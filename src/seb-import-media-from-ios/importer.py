from .media import MediaDb, MediaFile
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.exceptions import *
from pymobiledevice3.services.afc import AfcService, AfcException
from rich.progress import Progress
import posixpath
import logging
import xxhash
import os

logger = logging.getLogger(__name__)

MEDIA_FILEPATH = './DCIM'

class Importer:
    def __init__(self, import_dest):
        self.db = MediaDb()
        self.afc = None
        self.import_dest = import_dest
        self._connect()

    def _connect(self):
        try:
            lockdown = create_using_usbmux()
        except NoDeviceConnectedError as e:
            logger.critical('No device connected. Double check connection and retry.')
            return
        self.afc = AfcService(lockdown)

    def _walk(self, input_path, hashing=False):
        if not self.afc:
            logger.error('AFC connection not established yet, aborting')
            return
        for root, dirs, files in self.afc.walk(input_path):
            for f in sorted(files):
                filepath = posixpath.join(root, f)
                stat = self.afc.os_stat(filepath)
                yield dict(
                    filename=os.path.basename(filepath),
                    filepath_src=filepath,
                    size=stat.st_size,
                    time_ctime=stat.st_birthtime,
                    time_mtime=stat.st_mtime,
                )
    
    def scan(self):
        # Walk ./DCIM
        # Check each file against db
        # If present, check status:
            # If status = unimported, import
            # If status = imported, skip
        # If not present, add to db with 'unimported'
        count_skipped_imported_files = 0
        for fdata in self._walk(MEDIA_FILEPATH):
            media_file = self.db.get_mediafile_by_filepath(fdata['filepath_src'])
            if media_file:
                # Present in DB
                if media_file.status_imported:
                    count_skipped_imported_files += 1
                else:
                    # Queue it for import
                    if not media_file.status_queued:
                        self.db.update(fdata['filepath_src'], status_queued=True)
            else:
                # Not present in DB, add
                filepath_dst = os.path.join(self.import_dest, fdata['filepath_src'])
                self.db.add(
                    **fdata,
                    filepath_dst=filepath_dst,
                    status_imported=False,
                    status_queued=True,
                    status_verified=False,
                )
    
    def import_queued_files(self):
        # If file on disk present
            # Check filesize then hash
            # Mark as 'imported', or mark as 'skipped - file on disk'
        # If file on disk not present
            # Copy from device
        queue = self.db.get_mediafiles_queued()
        logger.info(f'Files queued: {len(queue)}')
        for media_file in queue:
            if os.path.isfile(media_file.filepath_dst):
                # Present on disk as expected. Remove from queue
                self.db.update(media_file.filepath_src, status_queued=False)
            else:
                # Not present, let's copy
                self.copy_file(
                    media_file.filepath_src,
                    media_file.filepath_dst,
                )

    def copy_file(self, filepath_src, filepath_dst, callback):
        logger.info(f"copy_file: {filepath_src} to {filepath_dst}")
        pass

    def verify_file(self, filepath, callback):
        pass