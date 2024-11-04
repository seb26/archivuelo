# Read all media folders on device, respecting user's exclusions
# Store in database and mark files as Queue for copy
# Copy, hash and show progress bar
# Mark as Completed in db
# (Optional) Async read back files 'verify' at destination




# CLI structure

scan
    --clear-db
    --reset-import-status
import [TARGET_DIR]
    --exclude-before
    --exclude-after
    --overwrite
    --force-all

* Database is stored in AppData

# Implementation of multithreading/async

* Copy process from USB device needs to be synchronous, single queue
* Verification process can be multi threaded. At the very least, verification needs to take place DURING copies, even if verification is 1-at-a-time itself
* CLI `import` command needs to wait until verification is complete before terminating


# FUTURE FEATURES:
verify
import
    --verify-only
    --skip-verify
    --videos-only
    --images-only
    --exclude "r/pattern/"
reset-status
    --exclude (all)

* More than one iOS device - provide mechanism to select