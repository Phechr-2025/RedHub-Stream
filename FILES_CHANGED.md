# Files changed in this revision

## Core runtime / menu

- `menuwed.py`
  - Rebuilt the main CLI
  - Added terminal input bindings to improve Backspace/Delete handling in interactive prompts
  - Reworked the web-info view to print the requested URL/status block with IP URL / Domain URL labels
  - Added best-effort firewall detection for the displayed status block
  - Added reverse-proxy setup for domain binding with nginx on 80/443 when sudo is available
  - Added the missing nginx path constants (`NGINX_SITE_AVAILABLE`, `NGINX_SITE_ENABLED`, `NGINX_SSL_DIR`) so domain binding can create certificates and site configs without a NameError
  - Added automatic certificate issuance via certbot / Let's Encrypt only; no self-signed fallback
  - Added automatic renewal setup for Let's Encrypt certificates
  - Added separate domain reachability vs. TLS-trust checks so the status block can tell the difference between “site is up” and “browser will trust the certificate”
  - Added local and domain health checks so the status block can detect Cloudflare / origin failures more accurately
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
  - Added best-effort port opening for 80/443 plus the app port when a domain is bound
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
  - Starts the web after install and prints the detailed status block
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

- Added `import re` to `menuwed.py` to fix `NameError: re is not defined`.
- Improved domain binding to auto-start the web app before applying nginx reverse proxy, reducing `502 Bad Gateway` from an offline upstream.

- `menuwed.py`
  - Added automatic Let's Encrypt renewal setup after successful certificate issuance
  - Added renewal hooks to stop/restart nginx during certbot renew so standalone HTTP-01 can complete
  - Added certbot timer enablement with cron fallback when systemd timer is unavailable
  - Cleaned up proxy removal to delete renewal hooks and cron fallback entries
