from .cache import Cache
from .device import Device
from .importer import Importer
from datetime import datetime
import asyncio
import click
import logging

logger = logging.getLogger(__name__)

@click.group()
@click.option('-v', '--verbose', is_flag=True, default=False, help="enable debugging output")
def archivuelo(verbose: bool):
    """
    Scans iOS device for media files (photos, videos, metadata sidecar files) and imports them into a directory of choice.
    """
    logging_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=logging_level,
        format='%(asctime)s | %(module)s.%(funcName)s[%(lineno)d] | %(message)s',
        datefmt='%H:%M:%S',
    )

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
        else:
            click.echo("Aborted, no changes made.")
        ctx.exit()
        return
    if reset_import_status:
        cache.reset_imported_status_on_all_files()
        ctx.exit()
        return
    device: Device = Device()
    importer: Importer = Importer()
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
    for option in [ 'exclude_before', 'exclude_after' ]:
        if options.get(option):
            try:
                options[option] = user_input_date(options[option])
                continue
            except ValueError:
                logger.error(f'Invalid format for option --{option}: \"{options[option]}\". Check and retry. Aborting.')
                ctx.exit()
    # Establish
    device: Device = Device()
    importer: Importer = Importer()
    # Import
    asyncio.run(
        importer.import_(device, target_dir, **options)
    )

def user_input_date(input: str) -> datetime:
    for format in [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ]:
        try:
            return datetime.strptime(input, format)
        except ValueError:
            continue
    raise ValueError(f"Could not parse '{input}' into a date & time object.")