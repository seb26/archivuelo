from .cache import Cache
from .device import Device
from .services import CopyService, VerifyService
from datetime import datetime
from functools import partial
from tqdm.asyncio import tqdm
import asyncio
import logging
import os

logger = logging.getLogger(__name__)

MEDIA_FILEPATH = './DCIM'


class Importer:
    def __init__(self):
        self.cache = Cache()
        self.copy_service = CopyService(self.cache)
        self.verify_service = VerifyService(self.cache)
        # Connect their queues
        self.copy_service.verify_queue = self.verify_service.queue
        self.verify_service.copy_queue = self.copy_service.queue

    def scan(self, device: Device):
        # As we identify files, check if they are tracked
        # And then queue them for copy, and apply any specified conditions
        logger.debug(f"Starting")
        count_scanned_files = 0 # Temporary
        count_tracked_files = 0
        count_untracked_files = 0
        for filepath in tqdm(
            device.get_media_files(MEDIA_FILEPATH),
            desc="Scanning",
            unit=" file",
        ):
            count_scanned_files += 1
            media_file = self.cache.get_file_from_filepath(filepath)
            if media_file:
                count_tracked_files += 1
                # Already cached - progress callback to display "found # tracked files"
                pass
            else:
                # Not yet cached, establish some basics about it
                stat = device.stat(filepath)
                media_file = self.cache.add(
                    filename=os.path.basename(filepath),
                    filepath_src=filepath,
                    size=stat.st_size,
                    time_birthtime=stat.st_birthtime,
                    time_mtime=stat.st_mtime,
                )
                count_untracked_files += 1
            yield media_file
        logger.debug(f"Scanned {count_scanned_files} files: {count_tracked_files} tracked, {count_untracked_files} untracked")
        

    async def import_(
        self,
        device: Device,
        target_directory: str,
        use_cache: bool=False,
        exclude_before: datetime=None,
        exclude_after: datetime=None,
        overwrite: bool=False,
        force_all: bool=False,
    ):
        logger.debug(f"Target directory: {target_directory}")
        if use_cache:
            logger.debug(f"Getting tracked unimported files from cache...")
            files = partial(self.cache.get_files_pending, force_all)
        else:
            logger.debug(f"Will perform device filesystem scan...")
            files = partial(self.scan, device)
        for media_file in files():
            # logger.debug(f"working on: {media_file.filepath_src}")
            # Filters
            if exclude_before:
                if media_file.time_birthtime <= exclude_before:
                    # logger.debug(f"Skipping based on filter: {media_file.filepath_src}")
                    continue
            if exclude_after:
                if media_file.time_birthtime >= exclude_after:
                    # logger.debug(f"Skipping based on filter: {media_file.filepath_src}")
                    continue
            # Add to the copy queue
            await self.copy_service.queue.put( (device, media_file, target_directory) )
            logger.debug("Added to copy queue")
        logger.debug(f"Queue counts | Copy: {self.copy_service.queue.qsize()} | Verify: {self.verify_service.queue.qsize()}")
        logger.debug("Adding tasks to Gather...")
        # Create ongoing tasks
        await asyncio.gather(
            self.copy_service.process_queue(),
            self.verify_service.process_queue(),
        )
        logger.debug("Added tasks to Gather.")
        logger.debug(f"Queue counts | Copy: {self.copy_service.queue.qsize()} | Verify: {self.verify_service.queue.qsize()}")
        # Watch for queue items
        logger.debug("Awaiting queue items...")
        await self.copy_service.queue.join()
        await self.verify_service.queue.join()
        logger.debug(f"Queue counts | Copy: {self.copy_service.queue.qsize()} | Verify: {self.verify_service.queue.qsize()}")