from enum import Enum, auto

class MediaStatus(Enum):
    UNIMPORTED = 0
    QUEUED_FOR_IMPORT = 10
    IMPORTED = 20

class MediaStatusVerification(Enum):
    UNVERIFIED = 0
    VERIFIED = 20