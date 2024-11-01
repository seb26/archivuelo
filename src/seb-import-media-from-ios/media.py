import peewee as pw

DB_FILEPATH = 'media.db'

db = pw.SqliteDatabase(
    DB_FILEPATH,
    pragmas={
        'journal_mode': 'wal',
    },
)

class BaseModel(pw.Model):
    class Meta:
        database = db

class MediaDb:
    def __init__(self):
        self.db = db
        self.db.connect()
        self.db.create_tables(
            [ MediaFile ],
            safe=True,
        )
    
    def is_present(self, media_id) -> bool:
        return bool( MediaFile.get_or_none(media_id=media_id) )
    
    def get_mediafile_by_filepath(self, filepath):
        """Lookup by AFC filepath"""
        return ( MediaFile
            .select(MediaFile)
            .where(MediaFile.filepath_src == filepath)
            .get_or_none()
        )
    
    def get_mediafiles_queued(self):
        """Lookup queued files"""
        return ( MediaFile
            .select(MediaFile)
            .where(MediaFile.status_queued is True)
            .get_or_none()
        )
    
    def add(self, **params):
        return MediaFile.create(**params)

    def update(self, filepath, **params):
        return ( MediaFile
            .insert(**params)
            .where(MediaFile.filepath_src == filepath)
            .on_conflict_replace()
            .execute()
        )

class MediaFile(BaseModel):
    id = pw.AutoField(primary_key=True)
    filename = pw.TextField()
    filepath_dst = pw.TextField(null=True)
    filepath_src = pw.TextField()
    hashvalue = pw.FixedCharField(null=True)
    size = pw.IntegerField()
    status_imported = pw.BooleanField(default=False)
    status_queued = pw.BooleanField(default=False)
    status_verified = pw.BooleanField(default=False)
    time_ctime = pw.TimestampField(null=True)
    time_import = pw.TimestampField(null=True)
    time_mtime = pw.TimestampField(null=True)
    time_verified = pw.TimestampField(null=True)