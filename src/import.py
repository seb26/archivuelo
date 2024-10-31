from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.afc import AfcService, AfcException

class Importer:
    def __init__(self):
        # Read back db

    def _connect(self):
        lockdown = create_using_usbmux()
        self.afc = AfcService(lockdown)
    
    def scan(self):
        # Walk ./DCIM
        # Check each file against db
        # If present, check status:
            # If status = unimported, import
            # If status = imported, skip
        # If not present, add to db with 'unimported'
        pass
    
    def import(self):
        # For all files with status 'unimported', import
        # If file on disk present
            # Check filesize then hash
            # Mark as 'imported', or mark as 'skipped - file on disk'
        # If file on disk not present
            # Copy from device
        pass

    def copy_file(self, filepath, callback):
        pass

    def verify_file(self, filepath, callback):
        pass