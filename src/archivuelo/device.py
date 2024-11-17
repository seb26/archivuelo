from .afc import AfcService
from pymobiledevice3.exceptions import *
from pymobiledevice3.lockdown import create_using_usbmux
import logging
import posixpath

logger = logging.getLogger(__name__)


class Device:
    def __init__(self):
        self._connect()

    def _connect(self):
        try:
            lockdown = create_using_usbmux()
        except PyMobileDevice3Exception as e:
            logger.debug('Exception', exc_info=e)
            logger.critical(f'Exception while trying to connect to device: {e.__class__.__qualname__}')
            raise e
        self.afc: AfcService = AfcService(lockdown)
        self.device_info = self.afc.lockdown.all_values
        d = self.device_info
        self.device_info_string = f"{d['DeviceClass']} \"{d['DeviceName']}\" (iOS {d['ProductVersion']})"
        logger.info(f"Connected to device: {self.device_info_string}")
        return True

    def get_media_files(self, input_path):
        for root, dirs, files in self.afc.walk(input_path):
            for filepath in sorted(files):
                yield posixpath.join(root, filepath)
    
    def pull_file(self, filepath_src, filepath_dst, callback):
        try:
            logger.debug(f"Pulling file FROM path {filepath_src} TO path {filepath_dst}")
            self.afc.pull(filepath_src, filepath_dst, callback=callback)
            return True
        except AfcException as e:
            logger.error(f'Error while pulling file FROM path {filepath_src} TO path {filepath_dst}', exc_info=e)
            return False

    def stat(self, filepath, **options):
        return self.afc.os_stat(filepath, **options)
