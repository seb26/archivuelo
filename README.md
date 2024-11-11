Scans iOS device for media files (photos, videos, metadata sidecar files) and imports them into a directory of choice.

Keeps track of files that have already been imported, and can filter which files to import based on date & time.

Alpha status.

Uses [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) to interface with iOS devices.

## Installation

* Clone the repo.
* Create and & activate a venv: `python -m venv .venv; activate`
* Install requirements: `pip install .`
* Run: `python -m import_media_ios.cli scan` and then `import`

## Tested on
Tested using Windows 11, Python 3.12 and an iOS 18.0 device (iPhone 16 Pro). The connections are USB-based, not wireless.

## Usage

### Common uses

Scan the connected iOS device for media files:

```python -m import_media_ios.cli scan```

Import the media to a directory of choice:

```python -m import_media_ios.cli import "C:\Users\me\Photos\iPhone_Media"```

### CLI

```
Usage: python -m import_media_ios.cli [OPTIONS] COMMAND [ARGS]...

Options:
  -v, --verbose  enable debugging output
  --help         Show this message and exit.

Commands:
  import
  scan
```

### import

```
Usage: python -m import_media_ios.cli import [OPTIONS] TARGET_DIR

Options:
  --exclude-before TEXT  Exclude all files with creation time before this
                         date (YYYY-MM-DD) or time (YYYY-MM-DD HH:MM:SS)
  --exclude-after TEXT   Exclude all files with creation time after this
                         date (YYYY-MM-DD) or time (YYYY-MM-DD HH:MM:SS)
  --force-all            Import all files, even if marked as imported
                         previously
  --overwrite            Overwrite existing files on disk
  --help                 Show this message and exit.
```

### scan
```
Usage: python -m import_media_ios.cli scan [OPTIONS]

Options:
  --clear-db             Clear the database and quit
  --reset-import-status  Force mark all files in the database to 'unimported'
  --help                 Show this message and exit.
```

## Development

[TODO.md](TODO.md)