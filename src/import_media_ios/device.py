from .afc import AfcService
from pymobiledevice3.exceptions import *
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.afc import MAXIMUM_READ_SIZE, AfcService
import logging
import os
import posixpath
import xxhash
from typing import Callable, Optional
from re import Pattern
import pathlib

logger = logging.getLogger(__name__)


class AfcService(AfcService):
    def __init__(self, *args, **kwargs):
        """Reclassed version of pymobiledevice3.services.afc, to permit derived functions"""
        super(AfcService, self).__init__(*args, **kwargs)

    def pull(
        self,
        relative_src: str,
        dst: str,
        match: Optional[Pattern] = None,
        callback: Optional[Callable] = None,
        src_dir: str = ''
    ) -> None:
            """
            Adapted pull() to include a hashing operation and exclude progress output
            """
            src = self.resolve_path(posixpath.join(src_dir, relative_src))

            if not self.isdir(src):
                # normal file
                if os.path.isdir(dst):
                    dst = os.path.join(dst, os.path.basename(relative_src))
                with open(dst, 'wb') as f:
                    hash = xxhash.xxh3_64()
                    src_size = self.stat(src)['st_size']
                    if src_size <= MAXIMUM_READ_SIZE:
                        chunk = self.get_file_contents(src)
                        f.write(chunk)
                        hash.update(chunk)
                    else:
                        left_size = src_size
                        handle = self.fopen(src)
                        chunk = self.fread(handle, min(MAXIMUM_READ_SIZE, left_size))
                        f.write(chunk)
                        hash.update(chunk)
                        left_size -= MAXIMUM_READ_SIZE
                        self.fclose(handle)
                os.utime(dst, (os.stat(dst).st_atime, self.stat(src)['st_mtime'].timestamp()))
                if callback is not None:
                    callback(src, dst, hash.hexdigest())
            else:
                # directory
                dst_path = pathlib.Path(dst) / os.path.basename(relative_src)
                dst_path.mkdir(parents=True, exist_ok=True)

                for filename in self.listdir(src):
                    src_filename = posixpath.join(src, filename)
                    dst_filename = dst_path / filename

                    src_filename = self.resolve_path(src_filename)

                    if match is not None and not match.match(posixpath.basename(src_filename)):
                        continue

                    if self.isdir(src_filename):
                        dst_filename.mkdir(exist_ok=True)
                        self.pull(src_filename, str(dst_path), callback=callback)
                        continue

                    self.pull(src_filename, str(dst_path), callback=callback)


class Device:
    def __init__(self):
        self._connect()

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

    async def get_media_files(self, input_path):
        for root, dirs, files in self.afc.walk(input_path):
            for filepath in sorted(files):
                yield posixpath.join(root, filepath)
    
    def pull_file(self, filepath_src, filepath_dst, callback):
        return self.afc.pull(filepath_src, filepath_dst, callback=callback)

    def stat(self, filepath, **options):
        return self.afc.os_stat(filepath, **options)
