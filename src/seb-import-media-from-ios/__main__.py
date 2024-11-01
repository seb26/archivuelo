from .importer import Importer
from .defaults import DESTINATION_DIRECTORY
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def main():
    # Functional order for now, CLI to come

    importer = Importer(
        import_dest=Path(DESTINATION_DIRECTORY),
    )
    # importer.scan()
    importer.import_pending_files(exclude_before=datetime(year=2024,month=10,day=30), overwrite=True)
    # importer.reset_imported_status()

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
        datefmt='%H:%M:%S',
    )
    main()