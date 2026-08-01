#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "menuwed_config.json"

DEFAULT_CONFIG = {
    "script_name": "menuwed",
    "project_name": "MySeriesVideo",
    "version": "latest",
    "github_repo": "Phechr-2025/RedHub-Stream",
    "install_path_unix": "~/menuwed",
    "install_path_windows": "%USERPROFILE%\\menuwed",
    "data_dir_unix": "~/menuwed-data",
    "data_dir_windows": "%USERPROFILE%\\menuwed-data",
    "venv_dir": ".venv",
    "service_name": "menuwed",
    "web_host": "0.0.0.0",
    "web_port": 5000,
    "env_file": ".env",
    "release_channel": "latest",
    "render_mode_envs": [
        "RENDER",
        "RAILWAY_PROJECT_ID",
        "RAILWAY_SERVICE_ID",
        "RAILWAY_ENVIRONMENT_ID",
        "RAILWAY_PUBLIC_DOMAIN",
    ],
}


def load_config() -> dict:
    config = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config.update(loaded)
        except Exception:
            pass
    return config


CONFIG = load_config()


def config_value(key: str, fallback: str = "") -> str:
    value = CONFIG.get(key, fallback)
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def expand_path(value: str) -> Path:
    value = str(value or "").strip()
    value = value.replace("%USERPROFILE%", str(Path.home()))
    return Path(os.path.expandvars(os.path.expanduser(value))).resolve()


def default_install_path() -> Path:
    key = "install_path_windows" if os.name == "nt" else "install_path_unix"
    return expand_path(config_value(key, DEFAULT_CONFIG[key]))


def default_data_dir() -> Path:
    key = "data_dir_windows" if os.name == "nt" else "data_dir_unix"
    return expand_path(config_value(key, DEFAULT_CONFIG[key]))


def default_venv_dir() -> str:
    return config_value("venv_dir", DEFAULT_CONFIG["venv_dir"])


def default_env_file_name() -> str:
    return config_value("env_file", DEFAULT_CONFIG["env_file"])


def project_name() -> str:
    return config_value("project_name", DEFAULT_CONFIG["project_name"])


def app_version() -> str:
    return config_value("version", DEFAULT_CONFIG["version"])


def github_repo() -> str:
    return config_value("github_repo", DEFAULT_CONFIG["github_repo"])


def latest_release_info(repo: str | None = None, tag: str | None = None) -> dict[str, str]:
    repo_name = (repo or github_repo()).strip()
    if not repo_name:
        raise RuntimeError("ไม่พบ github_repo")

    if tag and tag.startswith(("http://", "https://")):
        return {"tag_name": "", "zipball_url": tag, "name": "", "html_url": tag}

    if tag:
        api = f"https://api.github.com/repos/{repo_name}/releases/tags/{tag}"
    else:
        api = f"https://api.github.com/repos/{repo_name}/releases/latest"

    req = urllib.request.Request(api, headers={"User-Agent": "menuwed"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    zipball_url = str(data.get("zipball_url") or "").strip()
    if not zipball_url:
        raise RuntimeError("ไม่พบ zipball_url ใน release")

    resolved_tag = str(data.get("tag_name") or tag or "").strip()
    return {
        "tag_name": resolved_tag,
        "zipball_url": zipball_url,
        "name": str(data.get("name") or resolved_tag or tag or "").strip(),
        "html_url": str(data.get("html_url") or "").strip(),
    }


def read_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def write_env_file(path: Path, mapping: dict[str, str], header: str | None = None) -> None:
    lines: list[str] = []
    if header:
        lines.append(f"# {header}")
    for key, value in mapping.items():
        lines.append(f"{key}={value}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def env_defaults(
    project: str | None = None,
    version: str | None = None,
    data_dir: str | None = None,
    public_base_url: str | None = None,
    web_port: int | None = None,
) -> dict[str, str]:
    return {
        "SECRET_KEY": "change-this-to-a-random-secret",
        "PROJECT_NAME": project or project_name(),
        "APP_VERSION": version or app_version(),
        "PUBLIC_BASE_URL": public_base_url or "",
        "DATA_DIR": data_dir or str(default_data_dir()),
        "WEB_HOST": config_value("web_host", DEFAULT_CONFIG["web_host"]),
        "WEB_PORT": str(web_port or int(config_value("web_port", str(DEFAULT_CONFIG["web_port"])))),
        "SERVICE_NAME": config_value("service_name", DEFAULT_CONFIG["service_name"]),
        "VENV_DIR": default_venv_dir(),
        "TURNSTILE_SITE_KEY": "",
        "TURNSTILE_SECRET_KEY": "",
        "TURNSTILE_REQUIRED": "false",
        "TURNSTILE_ALLOWED_HOSTNAMES": "",
        "WEB_CONCURRENCY": "2",
        "GUNICORN_THREADS": "2",
        "GUNICORN_TIMEOUT": "120",
        "PORT": str(web_port or int(config_value("web_port", str(DEFAULT_CONFIG["web_port"])))),
        "FLASK_ENV": "production",
        "IS_PRODUCTION": "false",
    }


def sync_env_metadata(
    env_path: Path,
    *,
    project: str | None = None,
    version: str | None = None,
    data_dir: str | None = None,
    public_base_url: str | None = None,
    force_version: bool = True,
) -> None:
    current = read_env_file(env_path)
    current["PROJECT_NAME"] = project or project_name()
    if force_version or "APP_VERSION" not in current or not current["APP_VERSION"].strip():
        current["APP_VERSION"] = version or app_version()
    if data_dir:
        current["DATA_DIR"] = data_dir
    elif "DATA_DIR" not in current or not current["DATA_DIR"].strip():
        current["DATA_DIR"] = str(default_data_dir())
    if public_base_url is not None:
        current["PUBLIC_BASE_URL"] = public_base_url
    if "SECRET_KEY" not in current or not current["SECRET_KEY"].strip():
        current["SECRET_KEY"] = "change-this-to-a-random-secret"
    if "TURNSTILE_REQUIRED" not in current or not current["TURNSTILE_REQUIRED"].strip():
        current["TURNSTILE_REQUIRED"] = "false"
    if "VENV_DIR" not in current or not current["VENV_DIR"].strip():
        current["VENV_DIR"] = default_venv_dir()
    if "SERVICE_NAME" not in current or not current["SERVICE_NAME"].strip():
        current["SERVICE_NAME"] = config_value("service_name", DEFAULT_CONFIG["service_name"])
    if "PORT" not in current or not current["PORT"].strip():
        current["PORT"] = config_value("web_port", str(DEFAULT_CONFIG["web_port"]))
    if "WEB_PORT" not in current or not current["WEB_PORT"].strip():
        current["WEB_PORT"] = current["PORT"]
    if "WEB_HOST" not in current or not current["WEB_HOST"].strip():
        current["WEB_HOST"] = config_value("web_host", DEFAULT_CONFIG["web_host"])
    if "WEB_CONCURRENCY" not in current or not current["WEB_CONCURRENCY"].strip():
        current["WEB_CONCURRENCY"] = "2"
    if "GUNICORN_THREADS" not in current or not current["GUNICORN_THREADS"].strip():
        current["GUNICORN_THREADS"] = "2"
    if "GUNICORN_TIMEOUT" not in current or not current["GUNICORN_TIMEOUT"].strip():
        current["GUNICORN_TIMEOUT"] = "120"
    if "TURNSTILE_SITE_KEY" not in current:
        current["TURNSTILE_SITE_KEY"] = ""
    if "TURNSTILE_SECRET_KEY" not in current:
        current["TURNSTILE_SECRET_KEY"] = ""
    if "TURNSTILE_ALLOWED_HOSTNAMES" not in current:
        current["TURNSTILE_ALLOWED_HOSTNAMES"] = ""
    write_env_file(env_path, current, "Generated by menuwed")


def runtime_metadata(env_path: Path | None = None) -> dict[str, str]:
    values = read_env_file(env_path) if env_path else {}
    return {
        "project_name": values.get("PROJECT_NAME") or project_name(),
        "app_version": values.get("APP_VERSION") or app_version(),
        "data_dir": values.get("DATA_DIR") or str(default_data_dir()),
        "public_base_url": values.get("PUBLIC_BASE_URL", ""),
        "service_name": values.get("SERVICE_NAME") or config_value("service_name", DEFAULT_CONFIG["service_name"]),
    }
