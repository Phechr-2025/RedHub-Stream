# Files changed in this revision

## Core runtime / menu

- `menuwed.py`
  - Rebuilt the main CLI
  - Improved web startup to use the launcher script and verify the local health endpoint
  - Improved status output so it can detect a live server even when the PID file is missing or stale
  - Added root menu items:
    - uninstall
    - update latest
    - update specific tag / URL
    - update libraries
    - manage web
    - manage `.env`
  - Added background web process management with PID file
  - Added best-effort port opening
  - Added release update support that preserves data, `.env`, and venv
  - Added no-menu mode for remote / cloud environments

- `menuwed_meta.py`
  - Centralized config helpers
  - Added runtime metadata helpers
  - Added `venv_dir` support
  - Added `.env` generation / syncing helpers

- `menuwed_config.json`
  - Set version fallback to `latest`
  - Added `venv_dir`

## Installers

- `install.sh`
  - Better Linux bootstrap
  - Best-effort system dependency check
  - Creates install path and runs `menuwed.py install`
  - Creates PATH symlink
  - Shows web startup errors and status output instead of hiding them

- `install.ps1`
  - Windows bootstrap
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

- `.env.example`
  - Expanded to include runtime keys used by the installer and launcher

## Documentation

- `README.md`
  - Rewritten installation and usage instructions

## Notes

- Existing responsive CSS / media playback improvements were kept and the watch page continues to support both video and audio playback.
