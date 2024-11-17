# BUGS
* some PNGs have copied only half! aka top visual half is good image content and bottom visual half is white or black with no data (depending on png viewing app). however dest file hash matches! investigate
    * this is most likely not this app! pymobiledevice3 or iOS...


# Future
* Import pictures only, or videos only

* Import regex filters like `--exclude "r/pattern/"`

* When more than one iOS device, provide mechanism to select

# Structural

* Change away from tqdm back to rich

* Implementation of multithreading/async. Thoughts:
    * Copy process from USB device needs to be synchronous, single queue
    * Verification process can be multi threaded. At the very least, verification needs to take place DURING copies, even if verification is 1-at-a-time itself
    * CLI `import` command needs to wait for verification to complete before terminating