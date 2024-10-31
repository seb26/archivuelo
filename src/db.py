import peewee as pw

class MediaDb:
    def __init__(self):
        # Init db
        pass
    
    def add(self, **params):
        # Add or update
        pass

    def is_present(self, media) -> bool:
        # Lookup
        pass
    
    def update(self, **params):
        pass
    
class MediaFile(object):
    status = pw.IntegerField()
    status_verify = pw.IntegerField()
    filepath_src = pw.TextField()
    filepath_dst = pw.TextField()
    filename = pw.TextField()
    hashvalue = pw.FixedCharField()
    parent = pw.TextField()
    size = pw.IntegerField()
    mtime = pw.DateTimeField()
    ctime = pw.DateTimeField()
    import_time = pw.DateTimeField()
    verify_time = pw.DateTimeField()