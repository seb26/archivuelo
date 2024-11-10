from .importer import Importer
from datetime import datetime
import asyncio
import click
import logging

logger = logging.getLogger(__name__)

@click.group()
@click.pass_context
@click.option('-v', '--verbose', is_flag=True, default=False, help="enable debugging output")
def cli(ctx, verbose: bool):
    """CLI entrypoint"""
    logging_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=logging_level,
        format='%(asctime)s | %(message)s',
        datefmt='%H:%M:%S',
    )
    ctx.obj = Importer()
    if not ctx.obj.connection:
        ctx.exit()

@cli.command()
@click.pass_context
@click.pass_obj
@click.option('--clear-db', is_flag=True, default=False, help="Clear the database and quit")
@click.option('--reset-import-status', is_flag=True, default=False, help="Force mark all files in the database to 'unimported'")
def scan(importer, ctx, clear_db, reset_import_status, **options):
    if clear_db:
        click.echo("Clear the database of scanned media files.\n    (This does not affect any media files, neither on a device nor on disk.)")
        if click.confirm("Proceed to clear the database?"):
            click.echo("Clearing database...")
            importer.db.drop_db()
            click.echo("Clearing database: Done.")
        else:
            click.echo("Aborted, no changes made.")
        ctx.exit()
    if reset_import_status:
        importer.reset_imported_status()
        ctx.exit()
    importer.scan(**options)

@cli.command(name='import')
@click.pass_context
@click.pass_obj
@click.argument('target_dir')
@click.option('--exclude-before', help="Exclude all files with creation time before this time (YYYY-MM-DD HH:MM:SS)")
@click.option('--exclude-after', help="Exclude all files with creation time after this time (YYYY-MM-DD HH:MM:SS)")
@click.option('--force-all', is_flag=True, default=False, help="Import all files, even if marked as imported previously")
@click.option('--overwrite', is_flag=True, default=False, help="Overwrite existing files on disk")
def import_(importer, ctx, target_dir, **options):
    # Pre-parse dates
    for option in [ 'exclude_before', 'exclude_after' ]:
        if options.get(option):
            try:
                options[option] = user_input_date(options[option])
                continue
            except ValueError:
                logger.error(f'Invalid format for option --{option}: \"{options[option]}\". Check and retry. Aborting.')
                ctx.exit()
    # Do import
    asyncio.run(
        importer.import_(target_dir, **options)
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

if __name__ == "__main__":
    cli()