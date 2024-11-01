from .importer import Importer

def main():
    # Functional order for now, CLI to come

    importer = Importer(
        import_dest='C:\\Users\sebre\\Development\\_temp\\import_media_tmp',
    )
    importer.scan()
    importer.import_queued_files()

if __name__ == '__main__':
    main()