from .media import MediaDb, MediaFile
from .afc import AfcService
from datetime import datetime
from pathlib import Path, PurePosixPath 
from pymobiledevice3.exceptions import *
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.afc import AfcException
from rich.progress import ( TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, SpinnerColumn )
from rich.progress import Progress
from functools import partial
import asyncio
import logging
import humanize
import os
import posixpath
import xxhash
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

MEDIA_FILEPATH = './DCIM'
VERIFICATION_CHUNK_SIZE = 8192

progress_bar_components = (
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    TaskProgressColumn(),
    TimeElapsedColumn(),
    TextColumn("{task.completed} / {task.total} files"),
)

class Importer:
    def __init__(self):
        self.afc = None
        self.db = MediaDb()

        self.connection = self._connect()
        
        logger.info(f"Files present in database: {self.db.get_num_files()}")

        # Queues
        self.queue_copy = None
        self.queue_verify = None

    def _connect(self):
        try:
            lockdown = create_using_usbmux()
        except NoDeviceConnectedError as e:
            logger.critical('No device connected. Double check connection and retry.')
            return False
        self.afc = AfcService(lockdown)
        self.device_info = self.afc.lockdown.all_values
        d = self.device_info
        self.device_info_string = f"{d['DeviceClass']} \"{d['DeviceName']}\" (iOS {d['ProductVersion']})"
        logger.info(f"Connected to device: {self.device_info_string}")
        return True
    
    def scan(self):
        # Walk ./DCIM
        # Check each file against db
        # If present, check status:
            # If status = unimported, import
            # If status = imported, skip
        # If not present, add to db with 'unimported'
        def _walk(input_path):
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                SpinnerColumn(),
                TimeElapsedColumn(),
                TextColumn("{task.completed} / {task.total} files"),
            ) as progress:
                total_files = progress.add_task('Scanning media files', total=0, unit='files')
                for root, dirs, files in self.afc.walk(input_path):
                    # Update the total files in the master bar
                    progress.update(total_files, total=progress.tasks[total_files].total + len(files))
                    for f in sorted(files):
                        # Preserve exact path for use by pymobiledevice3
                        filepath_ios = posixpath.join(root, f)
                        if self.db.is_filepath_present(filepath_ios):
                            logger.debug(f"{filepath_ios} tracked in DB already")
                        stat = self.afc.os_stat(filepath_ios)
                        yield dict(
                            filename=os.path.basename(filepath_ios),
                            filepath_src=filepath_ios,
                            size=stat.st_size,
                            time_ctime=stat.st_birthtime,
                            time_mtime=stat.st_mtime,
                        )
                        progress.update(total_files, advance=1)

        count_skipped_imported_files = 0

        for fdata in _walk(MEDIA_FILEPATH):
            media_file = self.db.get_mediafile_by_filepath(fdata['filepath_src'])
            if media_file:
                # Present in DB
                if media_file.status_imported:
                    count_skipped_imported_files += 1
                else:
                    # Check if it on disk
                    if media_file.filepath_dst:
                        if Path(media_file.filepath_dst).is_file():
                            logger.debug(f"{media_file.filepath_src} exists on disk")
                        else:
                            # Mark as not yet imported
                            self.db.update(media_file.id, status_imported=False)
            else:
                # Not present in DB, add
                self.db.add(**fdata, status_imported=False)
    
    async def import_(
        self,
        target_dir: str,
        exclude_before: datetime=False,
        exclude_after: datetime=False,
        force_all: bool=False,
        overwrite: bool=False,
    ):
        applicable_files = self.db.get_mediafiles_pending(
            exclude_before=exclude_before,
            exclude_after=exclude_after,
            force_all=force_all,
        )
        if exclude_before:
            logger.info(f'Import: Will exclude files with creation date before: {exclude_before}')
        if exclude_after:
            logger.info(f'Import: Will exclude files with creation date after: {exclude_after}')
        if len(applicable_files) == 0:
            logger.error('Import: 0 files applicable to import. If needed, scan the device (again).')
        else:
            logger.info(f'Import: Files to import: {len(applicable_files)}')

        # Establish queue
        self.queue_verify = asyncio.Queue()
        # Create ongoing verification task
        verify_task = asyncio.ensure_future(self.verify_files())
        # Copy
        await self.copy_files(
            applicable_files,
            target_dir=target_dir,
            force_all=force_all,
            overwrite=overwrite,
        )
        # Wait until verify has completed all items
        await self.queue_verify.join()
        # Cancel tasks
        verify_task.cancel()

    async def copy_files(self, files_list, **options):
        count_files_copied = 0
        count_files_skipped = 0
        sum_bytes_copied = 0
        with Progress(*progress_bar_components) as progress:
            total = progress.add_task('Import', total=len(files_list))
            for media_file in files_list:
                filepath_dst = Path(options['target_dir']) / Path(media_file.filepath_src)
                if filepath_dst.is_file() and not options['overwrite']:
                    # Present on disk
                    logger.error(f"Import: {media_file.filepath_src}: already on disk")
                    count_files_skipped += 1
                else:
                    # Not present, let's copy
                    result = await self.copy_file(media_file, filepath_dst)
                    if result:
                        progress.update(total, advance=1)
                        count_files_copied += 1
                        sum_bytes_copied += media_file.size
        logger.info(f'Import: Complete. Files copied: {count_files_copied} ({humanize.naturalsize(sum_bytes_copied)}); Files skipped: {count_files_skipped}')

    async def copy_file(self, media_file, filepath_dst):
        def _on_pull_complete(src, dest, hash):
            # Save the destination filepath, and update statuses
            self.db.update(
                media_file.id,
                hashvalue=hash,
                filepath_dst=dest,
                status_imported=True,
                time_imported=datetime.now().timestamp(),
            )
    
        logger.debug(f"copy_file: {media_file.filepath_src} to {filepath_dst}")
        try:
            # Make directories first
            Path(filepath_dst).parent.mkdir(parents=True, exist_ok=True)
            # Read from source disk and write to destination
            self.afc.pull(
                media_file.filepath_src,
                filepath_dst,
                callback=_on_pull_complete,
            )
        except AfcException as e:
            logger.exception('Exception', exc_info=e)
            return False
        # Mark it for verify
        await self.queue_verify.put(media_file)
        return True

    async def verify_files(self):
        while True:
            logger.debug('verify_files() waiting...')
            media_file = await self.queue_verify.get()
            logger.debug(f'Got verify item from queue: {media_file.id}, {media_file.filename}')
            await self.verify_file(media_file)
            self.queue_verify.task_done()
            logger.debug(f'Verify queue size is now: {self.queue_verify.qsize()}')

    async def verify_file(self, media_file):
        if not Path(media_file.filepath_dst).is_file():
            logger.error(f'Verify: No file found at this path: {media_file.filepath_dst}')
            return False
        logger.debug(f'Verifying {media_file.filepath_dst} | Source hash: {media_file.hashvalue}')
        with open(media_file.filepath_dst, 'rb') as fbytes:
            dst_hasher = xxhash.xxh3_64()
            while chunk := fbytes.read(VERIFICATION_CHUNK_SIZE):
                dst_hasher.update(chunk)
            dst_hash = dst_hasher.hexdigest()
            if media_file.hashvalue == dst_hash:
                logger.debug(f'Verified match')
                return True
            else:
                logger.error(f'Verify: Hash mismatch for file {media_file.filepath_dst} - Source: {media_file.src_hash} - Destination: {dst_hash}')
                filesize_dst = Path(media_file.filepath_dst).stat().st_size
                logger.error(f'Verify: Destination filesize (bytes): {media_file.filepath_dst}')
                return False
            
    def reset_imported_status(self):
        rows = self.db.reset_imported()
        if rows:
            logger.info(f"Reset 'Imported' status for {rows} files.")