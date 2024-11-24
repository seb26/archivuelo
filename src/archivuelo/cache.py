import peewee as pw
import logging

logger = logging.getLogger(__name__)
logging.getLogger('peewee').setLevel(logging.INFO) # Quieten peewee logger

# TODO: make this user appdata not working directory lol
DB_FILEPATH = 'media.db'


if __name__ != '__main__':
    db = pw.SqliteDatabase(
        DB_FILEPATH,
        pragmas={
            'journal_mode': 'wal',
        },
    )


class BaseModel(pw.Model):
    class Meta:
        database = db


class TrackedMediaFile(BaseModel):
    id = pw.AutoField(primary_key=True)
    filename = pw.TextField()
    filepath_dst = pw.TextField(null=True, default=None)
    filepath_src = pw.TextField()
    hash_type = pw.TextField(null=True, default=None)
    hash_value = pw.FixedCharField(null=True)
    size = pw.IntegerField()
    status_imported = pw.BooleanField(default=False, null=True)
    status_verified = pw.BooleanField(default=False, null=True)
    time_birthtime = pw.TimestampField(default=None, null=True)
    time_imported = pw.TimestampField(default=None, null=True)
    time_mtime = pw.TimestampField(default=None, null=True)
    time_verified = pw.TimestampField(default=None, null=True)


class Cache:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        self.db = db
        self.db.connect(reuse_if_open=True)
        self.db.create_tables(tables, safe=True)

    def get_files_pending(self, force_all: bool=False):
        """
        Look up files scanned but not yet imported
        """
        # Get all files if force_all is defined
        condition = ( TrackedMediaFile.status_imported == False ) if not force_all else ( None )
        query = ( TrackedMediaFile
            .select(TrackedMediaFile)
            .where(condition)
        )
        if query:
            return list(query)
        else:
            logger.debug("No files pending")
            return list()

    def get_file_from_id(self, id):
        """Look up file from ID"""
        pass

    def get_file_from_filepath(self, filepath) -> TrackedMediaFile:
        """Look up file in cache from a device filepath"""
        return ( TrackedMediaFile
            .select(TrackedMediaFile)
            .where(TrackedMediaFile.filepath_src == filepath)
            .get_or_none()
        )

    def num_files(self) -> int:
        return TrackedMediaFile.select().count()
    
    def reset_imported_status_on_all_files(self):
        query = TrackedMediaFile.update(status_imported=False)
        return query.execute()

    def reset_cache(self):
        return self.db.drop_tables(TrackedMediaFile)
    
    def add(self, **params):
        media_file = TrackedMediaFile(**params)
        media_file.save()
        return media_file


tables = (
    TrackedMediaFile,
)