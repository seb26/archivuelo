from .media import MediaDb, MediaFile
from datetime import datetime
from pathlib import Path, PurePosixPath 
from pymobiledevice3.exceptions import *
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.afc import AfcService, AfcException
from rich.progress import ( TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, SpinnerColumn )
from rich.progress import Progress
from functools import partial
import asyncio
import logging
import os
import posixpath
import xxhash
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

MEDIA_FILEPATH = './DCIM'

progress_bar_components = (
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    TaskProgressColumn(),
    TimeElapsedColumn(),
    TextColumn("{task.completed} / {task.total} files"),
)

class Importer:
    def __init__(self):
        self.db = MediaDb()
        self.afc = None
        self.connection = self._connect()
        logger.info(f"Files present in database: {MediaFile.select().count()}")

        # Queues
        self.queue_verify = asyncio.Queue()
        self.queue_copy = asyncio.Queue()

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
    
    async def import_pending_files(
        self,
        target_dir: str,
        exclude_before: datetime=False,
        exclude_after: datetime=False,
        force_all: bool=False,
        overwrite: bool=False,
    ):
        def _callback_copy(media_file, filepath_src, filepath_dst):
            # Save the destination filepath, and update statuses
            self.db.update(
                media_file.id,
                hashvalue=hash,
                filepath_dst=filepath_dst,
                status_imported=True,
                time_imported=datetime.now().timestamp(),
            )

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
        count_files_copied = 0
        count_files_skipped = 0
        with Progress(*progress_bar_components) as progress:
            total = progress.add_task('Import', total=len(applicable_files))
            for media_file in applicable_files:
                filepath_dst = Path(target_dir) / Path(media_file.filepath_src)
                if filepath_dst.is_file() and not overwrite:
                    # Present on disk
                    logger.error(f"Import: {media_file.filepath_src}: already on disk")
                    count_files_skipped += 1
                else:
                    # Not present, let's copy
                    
                    await _callback_copy(
                        media_file,
                        filepath_dst=filepath_dst,
                    )
                        
            logger.info(f'Import: Complete. Files copied: {count_files_copied}; Files skipped: {count_files_skipped}')

    def copy_file(self, filepath_src, filepath_dst, callback=None):
        logger.debug(f"copy_file: {filepath_src} to {filepath_dst}")
        try:
            # Make directories first
            Path(filepath_dst).parent.mkdir(parents=True, exist_ok=True)
            # Pull
            result = self.afc.pull(
                filepath_src,
                filepath_dst,
                callback=callback,
            )
            return result
        except AfcException as e:
            logger.exception('Exception', exc_info=e)
            return False

    def queue_verify_file(self, **options):
        self.queue_verify_files.append(dict(**options))

    async def run_verify_files_queue(self):
        while len(self.queue_verify_files) > 0:
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {executor.submit(task, name): name for name in task_names}
                
                for future in as_completed(futures):

    def verify_file(self, filepath_src, filepath_dst, src_hash, src_filesize, callback=None):
        if not Path(filepath_dst).is_file():
            logger.error(f'Verify: No file found at this path: {filepath_dst}')
            return False
        with open(filepath_dst, 'rb') as fbytes:
            logger.debug(f'Verifying {filepath_dst} | Source hash: {src_hash}')
            dst_hasher = xxhash.xxh3_64()
            dst_hasher.update(fbytes)
            dst_hash = dst_hasher.hexdigest()
            if src_hash == dst_hash:
                logger.debug(f'Verified match')
                return True
            else:
                logger.error(f'Verify: Hash mismatch for file {filepath_dst} - Source: {src_hash} - Destination: {dst_hash}')
                filesize_dst = Path(filepath_dst).stat().st_size
                logger.error(f'Verify: Destination filesize (bytes): {filesize_dst}')
                return False

    def reset_imported_status(self):
        rows = self.db.reset_imported()
        if rows:
            logger.info(f"Reset 'Imported' status for {rows} files.")