import peewee as pw
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
# Quieten peewee logger
logging.getLogger('peewee').setLevel(logging.INFO)

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

    def get_num_files(self) -> int:
        return MediaFile.select().count()
    
    def is_filepath_present(self, filepath) -> bool:
        return bool( MediaFile.get_or_none(filepath_src=filepath) )
    
    def drop_db(self):
        return self.db.drop_tables(MediaFile)
    
    def reset_imported(self, where=None):
        query = MediaFile.update(status_imported=False)
        return query.execute()
    
    def get_mediafile_by_filepath(self, filepath):
        """Lookup by AFC filepath"""
        return ( MediaFile
            .select(MediaFile)
            .where(MediaFile.filepath_src == filepath)
            .get_or_none()
        )
    
    def get_mediafiles_pending(self, exclude_before: datetime=False, exclude_after: datetime=False, force_all: bool=False):
        """Lookup queued files"""
        if force_all:
            query = MediaFile.select()
        else:
            query = ( MediaFile
                .select()
                .where(MediaFile.status_imported == False)
            )
        if exclude_before:
            query = query.where(MediaFile.time_ctime >= exclude_before)
        if exclude_after:
            query = query.where(MediaFile.time_ctime <= exclude_after)
        if query:
            return list(query)
        else:
            return []
    
    def add(self, **params):
        return MediaFile.create(**params)

    def update(self, id, **params):
        return ( MediaFile
            .update(**params)
            .where(MediaFile.id == id)
            .execute()
        )

class MediaFile(BaseModel):
    id = pw.AutoField(primary_key=True)
    filename = pw.TextField()
    filepath_dst = pw.TextField(null=True, default=None)
    filepath_src = pw.TextField()
    hashvalue = pw.FixedCharField(null=True)
    size = pw.IntegerField()
    status_imported = pw.BooleanField(default=None, null=True)
    status_verified = pw.BooleanField(default=None, null=True)
    time_ctime = pw.TimestampField(default=None, null=True)
    time_imported = pw.TimestampField(default=None, null=True)
    time_mtime = pw.TimestampField(default=None, null=True)
    time_verified = pw.TimestampField(default=None, null=True)