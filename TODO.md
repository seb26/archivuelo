# rough initial plan

* Read all media folders on device, respecting user's exclusions
* Store in database and mark files as Queue for copy
* Copy, hash and show progress bar
* Mark as Completed in db
* (Optional) Async read back files 'verify' at destination


# improvements

* Change the project's name to something easier
* Fix CLI entrypoint so that it is as simple as `projectname import` and `projectname scan` instead of cli suffix
* Make `import` run a scan if one is not present

# CLI structure

import [TARGET_DIR]
    --no-scan
    --exclude-before
    --exclude-after
    --overwrite
    --force-all
scan
    --clear-db
    --reset-import-status

* Database is stored in AppData

* Import runs a scan by default

# Implementation of multithreading/async

* Copy process from USB device needs to be synchronous, single queue
* Verification process can be multi threaded. At the very least, verification needs to take place DURING copies, even if verification is 1-at-a-time itself
* CLI `import` command needs to wait for verification to complete before terminating


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