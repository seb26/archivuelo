from .cache import Cache, TrackedMediaFile
from .device import Device
from .filters import FileFilterTimeAfter, FileFilterTimeBefore
from .importer import Importer
from importlib.metadata import version
from pymobiledevice3.exceptions import PyMobileDevice3Exception
from tqdm.asyncio import tqdm
import asyncio
import click
import logging

logger = logging.getLogger('archivuelo')


MAP_CLI_PARAMETERS_TO_FILTERS = {
    'exclude_after': FileFilterTimeAfter,
    'exclude_before': FileFilterTimeBefore,
}

class CustomFormatter(logging.Formatter):
    """Logging colored formatter, adapted from https://stackoverflow.com/a/56944256/3638629"""

    grey = '\x1b[38;21m'
    blue = '\x1b[38;5;39m'
    yellow = '\x1b[38;5;226m'
    red = '\x1b[38;5;196m'
    reset = '\x1b[0m'

    def __init__(self, fmt):
        super().__init__()
        self.fmt = fmt
        self.datefmt = "%H:%M:%S"
        self.FORMATS = {
            logging.DEBUG: self.grey + self.fmt + self.reset,
            logging.INFO: self.blue + self.fmt + self.reset,
            logging.WARNING: self.yellow + self.fmt + self.reset,
            logging.ERROR: self.red + self.fmt + self.reset,
            logging.CRITICAL: self.red + self.fmt + self.reset
        }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        formatter.datefmt = self.datefmt
        return formatter.format(record)


def get_device(ctx: click.Context) -> Device:
    """
    param ctx: provide Click context to allow this function to quit Click on exceptions
    """
    try:
        device: Device = Device()
        return device
    except PyMobileDevice3Exception:
        logger.critical('Quitting. Unable to connect to device. Ensure connection then retry. Run with --verbose to see traceback.')
        ctx.exit(2)


@click.group()
@click.option('-v', '--verbose', is_flag=True, default=False, help="enable debugging output")
def archivuelo(verbose: bool):
    """
    Scans iOS device for media files (photos, videos, metadata sidecar files) and imports them into a directory of choice.
    """

    # Establish logging
    if verbose:
        user_level = logging.DEBUG
        fmt = "%(asctime)s | %(module)s.%(funcName)s[%(lineno)d] | %(message)s"
    else:
        user_level = logging.INFO
        fmt = "%(asctime)s | %(message)s"
    logger.setLevel(user_level)
    handler_stdout = logging.StreamHandler()
    handler_stdout.setLevel(user_level)
    handler_stdout.setFormatter(CustomFormatter(fmt=fmt))
    logger.addHandler(handler_stdout)
    logger.info(f"archivuelo {version('archivuelo')}")
    
@archivuelo.command()
@click.pass_context
@click.option('--clear-db', is_flag=True, default=False, help="Clear the database and quit")
@click.option('--reset-import-status', is_flag=True, default=False, help="Force mark all files in the database to 'unimported'")
def scan( ctx, clear_db, reset_import_status, **options):
    cache: Cache = Cache()
    if clear_db:
        click.echo("Clear the database of scanned media files.\n    (This does not affect any media files, neither on a device nor on disk.)")
        if click.confirm("Proceed to clear the database?"):
            click.echo("Clearing database...")
            cache.reset_cache()
            click.echo("Clearing database: Done.")
            ctx.exit(0)
        else:
            click.echo("Aborted, no changes made.")
            ctx.exit(127)
        return
    if reset_import_status:
        cache.reset_imported_status_on_all_files()
        ctx.exit(0)
        return
    device = get_device(ctx)
    importer = Importer()
    for f in importer.scan(device, **options):
        pass

@archivuelo.command(name='import')
@click.pass_context
@click.argument('target_dir')
@click.option('--exclude-after', help="Exclude all files with creation time after this date (YYYY-MM-DD) or time (YYYY-MM-DD HH:MM:SS)")
@click.option('--exclude-before', help="Exclude all files with creation time before this date (YYYY-MM-DD) or time (YYYY-MM-DD HH:MM:SS)")
@click.option('--force-all', is_flag=True, default=False, help="Import all files, even if marked as imported previously")
@click.option('--overwrite', is_flag=True, default=False, help="Overwrite existing files on disk")
@click.option('--use-cache', is_flag=True, help="Don't scan the device and perform import only using already tracked items")
def import_(ctx, target_dir, **options):
    # Pre-parse dates into datetime objects
    options['exclude_filters'] = []
    for cli_option, filter_class in MAP_CLI_PARAMETERS_TO_FILTERS.items():
        # If defined by user
        if options.get(cli_option):
            try:
                filter = filter_class(TrackedMediaFile.time_birthtime, options[cli_option])
            except ValueError:
                logger.error(f'Invalid format for option --{cli_option}: \"{options[cli_option]}\". Check and retry. Aborting.')
                ctx.exit(1)
            options['exclude_filters'].append(filter)
            options.pop(cli_option)
    # Establish
    device = get_device(ctx)
    importer = Importer()
    # Import
    asyncio.run(
        importer.import_(device, target_dir, **options)
    )