# Files changed in this revision

## Core runtime / menu

- `menuwed.py`
  - Rebuilt the main CLI
  - Added terminal input bindings to improve Backspace/Delete handling in interactive prompts
  - Reworked the web-info view to print the requested URL/status block
  - Improved web startup to use the launcher script and verify the local health endpoint
  - Improved status output so it can detect a live server even when the PID file is missing or stale
  - Added root menu items:
    - uninstall
    - update latest
    - update specific tag / URL
    - update libraries
    - manage web
    - manage config
  - Added background web process management with PID file
  - Added best-effort port opening
  - Added safer release updates that sync the release tree, preserve local state, and restart the web if it was running
  - Added no-menu mode for remote / cloud environments

- `menuwed_meta.py`
  - Centralized config helpers
  - Added runtime metadata helpers
  - Added `venv_dir` support
  - Added config generation / syncing helpers

- `menuwed_config.json`
  - Set version fallback to `latest`
  - Added `venv_dir`

## Installers

- `install.sh`
  - Better Linux bootstrap
  - Clearer download / extract / install progress messages
  - Best-effort system dependency check
  - Creates install path and runs `menuwed.py install`
  - Starts the web after install and prints the requested centered summary block
  - Creates PATH symlink
  - Shows web startup errors and status output instead of hiding them

- `install.ps1`
  - Windows bootstrap
  - Clearer download / extract / install progress messages
  - Downloads latest release
  - Copies files and runs `menuwed.py install`
  - Creates user PATH shim

## App / deploy

- `app.py`
  - Turnstile default changed to non-mandatory
  - This prevents startup crashes when keys are not configured

- `start.sh`
  - Uses the project venv first when available
  - Runs `gunicorn` through the venv Python
  - Falls back to the venv Python directly before system Python

## Environment

- `menuwed_config.json`
  - Expanded to include runtime keys used by the installer and launcher

## Documentation

- `README.md`
  - Rewritten installation and usage instructions

## Notes

- Existing responsive CSS / media playback improvements were kept and the watch page continues to support both video and audio playback.
