from .cache import Cache
from .device import Device
from datetime import datetime
from pathlib import Path
import asyncio
import logging
import humanize
import os
import xxhash

logger = logging.getLogger(__name__)

MEDIA_FILEPATH = './DCIM'
VERIFICATION_CHUNK_SIZE = 8192


class Importer:
    def __init__(self):
        self.cache = Cache()
        self.copy_service = CopyService(self.cache)
        self.verify_service = VerifyService(self.cache)

    async def import_(self, device: Device, exclude_before: datetime=None, exclude_after: datetime=None):

        def _on_scan(**data):
            pass

        # As we identify files, check if they are tracked
        # And then queue them for copy, and apply any specified conditions
        async for filepath in device.get_media_files(
            MEDIA_FILEPATH,
            self.cache,
        ):
            media_file = self.cache.get_file_from_filepath(filepath)
            if media_file:
                # Already cached
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
            # Add to copy queue
            if exclude_before:
                pass #logic
            await self.copy_service.queue.put(media_file)

class CopyService:
    def __init__(self, cache):
        self.cache = cache
        self.queue = asyncio.Queue()

    async def process_queue(self, verify_queue, verify_files_after: bool=True):
        while not self.queue.empty():
            media_file = await self.queue.get()
            result, src_hash = await self.pull_file_from_device(
                media_file.filepath_src,
                media_file.filepath_dst,
            )
            # Issue with copy
            if not result:
                pass
            # Add to verify queue
            if verify_queue and verify_files_after:
                # Refresh our cache row
                media_file = self.cache.get_file_from_id(media_file.id)
                await verify_queue.put(media_file, src_hash)
            # Update the tracked file
            self.queue.task_done()

    async def pull_file_from_device(self, device, filepath_src, filepath_dst, progress_callback=None):
        """Perform the pull"""
        src_hash = None
        def _on_pull_complete(src, dest, hash=src_hash):
            # Update db
            self.cache.upsert(
                filepath_src=src,
                filepath_dst=dest,
                hashvalue=hash,
                status_imported=True,
                time_imported=datetime.now(),
            )
        result = device.pull_file(filepath_src, filepath_dst, _on_pull_complete)
        return result, src_hash


class VerifyService:
    def __init__(self, cache):
        self.cache = cache
        self.queue = asyncio.Queue()

    async def process_queue(self, copy_queue):
        while not copy_queue.empty() and not self.queue.empty():
            media_file, src_hash = await self.queue.get()
            file_is_verified = await self.verify_file_on_disk(media_file, src_hash)
            self.queue.task_done()
    
    async def verify_file_on_disk(self, media_file, src_hash) -> bool:
        """Check file on disk against src hash, src filesize"""
        if not Path(media_file.filepath_dst).is_file():
            logger.error(f'Verify: No file found at this path: {media_file.filepath_dst}')
            return False
        logger.debug(f'Verifying {media_file.filepath_dst} | Source hash: {src_hash}')
        with open(media_file.filepath_dst, 'rb') as fbytes:
            dst_hasher = xxhash.xxh3_64()
            while chunk := fbytes.read(VERIFICATION_CHUNK_SIZE):
                dst_hasher.update(chunk)
            dst_hash = dst_hasher.hexdigest()
            if src_hash == dst_hash:
                logger.debug(f'Verified match')
                return True
            else:
                logger.error(f'Verify: Hash mismatch for file {media_file.filepath_dst} - Source: {media_file.src_hash} - Destination: {dst_hash}')
                filesize_dst = Path(media_file.filepath_dst).stat().st_size
                logger.error(f'Verify: Destination filesize (bytes): {media_file.filepath_dst}')
                return False