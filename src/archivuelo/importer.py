from .cache import Cache, TrackedMediaFile
from .device import Device
from .filters import FileFilter
from .services import CopyService, VerifyService
from .utils import ProgressBar
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import List, Generator
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

    def scan(self, device: Device) -> Generator[TrackedMediaFile, None, None]:
        # As we identify files, check if they are tracked
        # And then queue them for copy, and apply any specified conditions
        logger.debug(f"Starting")
        count_scanned_files = 0 # Temporary
        count_tracked_files = 0
        count_untracked_files = 0
        for filepath in tqdm(
            device.get_media_files(MEDIA_FILEPATH),
            desc="Scanning",
            unit=" files",
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
        exclude_filters: List[FileFilter]=[],
        exclude_after: datetime=None,
        overwrite: bool=False,
        force_all: bool=False,
    ):
        logger.info(f"Will import to directory: {target_directory}")
        if use_cache:
            logger.debug(f"Getting tracked unimported files from cache...")
            files = partial(self.cache.get_files_pending, force_all)
        else:
            logger.debug(f"Will perform device filesystem scan...")
            files = partial(self.scan, device)
        pbar_import = tqdm(desc='Will import', unit=' files')
        pbar_skipping_exists = tqdm(desc='Will skip (already on disk)', unit=' files')
        for media_file in files():
            # Test all provided filters
            filter_was_triggered = False
            for exclude_filter in exclude_filters:
                filter_result = exclude_filter.test_filter(media_file)
                if filter_result.result is False:
                    filter_was_triggered = True
                    logger.debug(f"Matches exclude filter [{exclude_filter}: {exclude_filter.compare_value}] | File: {media_file.filepath_src} | {filter_result.get_test_results_as_str()}")
                    break
            if filter_was_triggered:
                continue
            # Test files already on disk
            if overwrite:
                logger.info("Overwrite is ON: all files eligible for import will be copied by overwriting existing files on disk")
            else:
                # Establish destination filepath
                filepath_dst = Path(target_directory) / Path(media_file.filepath_src)
                if filepath_dst.is_file():
                    logger.debug(f"File exists, skipping: {filepath_dst}")
                    pbar_skipping_exists.update(1)
                    continue
            # Add to the copy queue
            await self.copy_service.queue.put( (device, media_file, target_directory) )
            logger.debug("Added to copy queue")
            pbar_import.update(1)
        logger.debug(f"Queue counts | Copy: {self.copy_service.queue.qsize()} | Verify: {self.verify_service.queue.qsize()}")
        pbar_copy = ProgressBar(name='Copying', unit=' files', total=self.copy_service.queue.qsize())
        pbar_verify = ProgressBar(name='Verifying', unit=' files')
        # Create ongoing tasks
        await asyncio.gather(
            self.copy_service.process_queue(pbar_copy.update),
            self.verify_service.process_queue(pbar_verify.update),
        )
        # Update Verify total based on qsize
        pbar_verify.total = self.verify_service.queue.qsize()
        # Watch for queue items
        await self.copy_service.queue.join()
        await self.verify_service.queue.join()