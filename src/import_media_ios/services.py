from .cache import Cache, TrackedMediaFile
from .device import Device
from datetime import datetime
from pathlib import Path
from functools import partial
import asyncio
import logging
import xxhash

logger = logging.getLogger(__name__)

VERIFICATION_CHUNK_SIZE = 8192


class CopyService:
    def __init__(self, cache):
        self.cache: Cache = cache
        self.queue = asyncio.Queue()
        self.verify_queue: asyncio.Queue = None

    async def process_queue(self, verify_files_after: bool=True):
        while not self.queue.empty():
            device, media_file, target_directory = await self.queue.get()
            result, media_file = await self.copy_file_from_device(device, media_file, target_directory)
            # Issue with copy
            if not result:
                logger.error(f"Pull file unsucessful: {media_file.filepath_src}")
                raise Exception()
                self.queue.task_done()
            # Add to verify queue
            if verify_files_after and self.verify_queue:
                # Refresh our cache row
                # media_file = self.cache.get_file_from_id(media_file.id)
                await self.verify_queue.put(media_file)
            # Update the tracked file
            self.queue.task_done()

    async def copy_file_from_device(self, device: Device, media_file, target_directory: str, progress_callback=None):
        """
        Perform the pull and update db afterwards
        """
        def _on_pull_complete(media_file: TrackedMediaFile, src: str, dest: str, hash: str):
            """
            param media_file: TrackedMediaFile
            param src, dest, hash: from afc.pull() callback
            """
            media_file.filepath_dst = dest
            media_file.hash_type = hash['type']
            media_file.hash_value = hash['value']
            media_file.status_imported = True
            media_file.time_imported = datetime.now()
            media_file.save()

        result = device.pull_file(
            media_file.filepath_src,
            target_directory,
            partial(_on_pull_complete, media_file),
        )
        return (result, media_file)


class VerifyService:
    def __init__(self, cache):
        self.cache = cache
        self.queue = asyncio.Queue()
        self.copy_queue: asyncio.Queue = None

    async def process_queue(self):
        while not self.copy_queue.empty() and not self.queue.empty():
            media_file = await self.queue.get()
            file_is_verified = await self.verify_file_on_disk(media_file)
            self.queue.task_done()
    
    async def verify_file_on_disk(self, media_file) -> bool:
        """
        Check file on disk against src hash, src filesize
        """
        if not media_file.get('hash_value'):
            logger.error(f'Verify: No hash value found for this media file: {media_file.filepath_src}')
            return False
        if not media_file.get('hash_type') == 'xxh3_64':
            logger.error(f"Verify: Unrecognised hash type ({media_file.get('hash_type')}) for this media file, can't verify: {media_file.filepath_src}")
            return False
        if not Path(media_file.filepath_dst).is_file():
            logger.error(f'Verify: No file found at this path: {media_file.filepath_dst}')
            return False
        logger.debug(f'Verifying {media_file.filepath_dst} | Source hash: {media_file.hash_value} ({media_file.hash_type})')
        with open(media_file.filepath_dst, 'rb') as fbytes:
            dst_hasher = xxhash.xxh3_64()
            while chunk := fbytes.read(VERIFICATION_CHUNK_SIZE):
                dst_hasher.update(chunk)
            dst_hash = dst_hasher.hexdigest()
            if media_file.hashvalue == dst_hash:
                logger.debug(f'Verified match')
                return True
            else:
                logger.error(f'Verify: Hash mismatch for file {media_file.filepath_dst} - Source: {media_file.hashvalue} - Destination: {dst_hash}')
                filesize_dst = Path(media_file.filepath_dst).stat().st_size
                logger.error(f'Verify: Destination filesize (bytes): {media_file.filepath_dst}')
                return False