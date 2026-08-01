#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Iterable

from menuwed_meta import (
    CONFIG,
    BASE_DIR,
    app_version as config_app_version,
    default_data_dir,
    default_env_file_name,
    default_install_path,
    default_venv_dir,
    env_defaults,
    github_repo,
    latest_release_info,
    project_name as config_project_name,
    read_env_file,
    runtime_metadata,
    sync_env_metadata,
    write_env_file,
)

SCRIPT_NAME = CONFIG.get("script_name", "menuwed")
INSTALL_PATH = default_install_path()

ENV_FILE = INSTALL_PATH / default_env_file_name()
VENV_DIR = INSTALL_PATH / default_venv_dir()
PID_FILE = INSTALL_PATH / ".menuwed-web.pid"
LOG_DIR = INSTALL_PATH / "logs"
WEB_LOG_FILE = LOG_DIR / "web.log"
MARKER_FILE = INSTALL_PATH / ".menuwed-installed"
RELEASE_CHANNEL = CONFIG.get("release_channel", "latest")
RENDER_MODE_ENVS = {str(x).strip() for x in CONFIG.get("render_mode_envs", []) if str(x).strip()}
SYSTEM_HOST = CONFIG.get("web_host", "0.0.0.0")
SYSTEM_PORT = int(CONFIG.get("web_port", 5000))

APP_PATH = BASE_DIR / "app.py"
REQUIREMENTS_PATH = BASE_DIR / "requirements.txt"


def expand_path(value: str) -> Path:
    value = str(value or "").strip()
    value = value.replace("%USERPROFILE%", str(Path.home()))
    return Path(os.path.expandvars(os.path.expanduser(value))).resolve()


def install_root() -> Path:
    return expand_path(CONFIG.get("install_path_windows") if os.name == "nt" else CONFIG.get("install_path_unix"))


def data_root() -> Path:
    env = read_env_file(env_path()) if env_path().exists() else {}
    value = os.getenv("DATA_DIR") or env.get("DATA_DIR")
    if not value:
        value = CONFIG.get("data_dir_windows") if os.name == "nt" else CONFIG.get("data_dir_unix")
    return expand_path(value)


def is_remote_mode() -> bool:
    return any(os.getenv(name) for name in RENDER_MODE_ENVS)


def env_path() -> Path:
    return INSTALL_PATH / default_env_file_name()


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def venv_pip() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "pip.exe"
    return VENV_DIR / "bin" / "pip"


def is_process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def read_pid() -> int | None:
    try:
        if PID_FILE.exists():
            value = PID_FILE.read_text(encoding="utf-8").strip()
            if value:
                return int(value)
    except Exception:
        return None
    return None


def write_pid(pid: int) -> None:
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(pid), encoding="utf-8")


def clear_pid() -> None:
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def current_env() -> dict[str, str]:
    env = os.environ.copy()
    if env_path().exists():
        env.update(read_env_file(env_path()))
    env["DATA_DIR"] = str(data_root())
    env.setdefault("PROJECT_NAME", env.get("PROJECT_NAME") or config_project_name())
    env.setdefault("APP_VERSION", env.get("APP_VERSION") or config_app_version())
    env.setdefault("PORT", env.get("PORT") or env.get("WEB_PORT") or str(SYSTEM_PORT))
    env.setdefault("WEB_PORT", env.get("WEB_PORT") or env["PORT"])
    env.setdefault("WEB_HOST", env.get("WEB_HOST") or SYSTEM_HOST)
    return env


def local_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
        finally:
            sock.close()
    except Exception:
        return "127.0.0.1"


def public_url() -> str:
    env = read_env_file(env_path())
    if env.get("PUBLIC_BASE_URL"):
        return env["PUBLIC_BASE_URL"].rstrip("/")
    port = env.get("PORT") or env.get("WEB_PORT") or str(SYSTEM_PORT)
    host = local_ip()
    return f"http://{host}:{port}"


def web_command() -> list[str]:
    """Return the preferred launch command for the website."""
    if os.name != "nt":
        launcher = BASE_DIR / "start.sh"
        if launcher.exists():
            return ["sh", str(launcher)]
    return [str(runtime_python()), str(APP_PATH)]


def check_local_web_ready(port: int, timeout: float = 2.0) -> bool:
    """Best-effort readiness check against the local HTTP endpoint."""
    url = f"http://127.0.0.1:{int(port)}/healthz"
    req = urllib.request.Request(url, headers={"User-Agent": SCRIPT_NAME})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= getattr(resp, "status", 200) < 400
    except Exception:
        pass
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=timeout):
            return True
    except Exception:
        return False


def tail_log_file(path: Path, lines: int = 40) -> str:
    try:
        data = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(data[-lines:])
    except Exception:
        return ""


def ensure_dirs() -> None:
    INSTALL_PATH.mkdir(parents=True, exist_ok=True)
    data_root().mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def ensure_env(force: bool = False) -> Path:
    ensure_dirs()
    target = env_path()

    defaults = env_defaults(
        project=os.getenv("PROJECT_NAME") or config_project_name(),
        version=os.getenv("APP_VERSION") or config_app_version(),
        data_dir=str(data_root()),
        public_base_url=os.getenv("PUBLIC_BASE_URL", ""),
        web_port=int(os.getenv("PORT") or os.getenv("WEB_PORT") or SYSTEM_PORT),
    )
    current = read_env_file(target)

    if target.exists() and not force:
        merged = dict(current)
        for key, value in defaults.items():
            if key not in merged or not str(merged[key]).strip():
                merged[key] = value
        merged["PROJECT_NAME"] = merged.get("PROJECT_NAME") or config_project_name()
        merged["APP_VERSION"] = merged.get("APP_VERSION") or config_app_version()
        merged["DATA_DIR"] = merged.get("DATA_DIR") or str(data_root())
        merged["PORT"] = str(int(os.getenv("PORT") or os.getenv("WEB_PORT") or merged.get("PORT") or SYSTEM_PORT))
        merged["WEB_PORT"] = merged["PORT"]
        merged["WEB_HOST"] = merged.get("WEB_HOST") or SYSTEM_HOST
        merged["VENV_DIR"] = merged.get("VENV_DIR") or default_venv_dir()
        merged["SERVICE_NAME"] = merged.get("SERVICE_NAME") or CONFIG.get("service_name", SCRIPT_NAME)
        merged["TURNSTILE_REQUIRED"] = merged.get("TURNSTILE_REQUIRED") or "false"
        merged["TURNSTILE_SITE_KEY"] = merged.get("TURNSTILE_SITE_KEY") or ""
        merged["TURNSTILE_SECRET_KEY"] = merged.get("TURNSTILE_SECRET_KEY") or ""
        merged["TURNSTILE_ALLOWED_HOSTNAMES"] = merged.get("TURNSTILE_ALLOWED_HOSTNAMES") or ""
        merged["WEB_CONCURRENCY"] = merged.get("WEB_CONCURRENCY") or "2"
        merged["GUNICORN_THREADS"] = merged.get("GUNICORN_THREADS") or "2"
        merged["GUNICORN_TIMEOUT"] = merged.get("GUNICORN_TIMEOUT") or "120"
        merged["SECRET_KEY"] = merged.get("SECRET_KEY") or "change-this-to-a-random-secret"
        merged["PUBLIC_BASE_URL"] = merged.get("PUBLIC_BASE_URL") or ""
        if merged != current:
            write_env_file(target, merged, "Generated by menuwed")
        return target

    merged = dict(defaults)
    merged.update(current)
    merged["PROJECT_NAME"] = os.getenv("PROJECT_NAME") or merged.get("PROJECT_NAME") or config_project_name()
    merged["APP_VERSION"] = os.getenv("APP_VERSION") or merged.get("APP_VERSION") or config_app_version()
    merged["DATA_DIR"] = str(data_root())
    merged["PORT"] = str(int(os.getenv("PORT") or os.getenv("WEB_PORT") or merged.get("PORT") or SYSTEM_PORT))
    merged["WEB_PORT"] = merged["PORT"]
    merged["WEB_HOST"] = os.getenv("WEB_HOST") or merged.get("WEB_HOST") or SYSTEM_HOST
    merged["VENV_DIR"] = merged.get("VENV_DIR") or default_venv_dir()
    merged["SERVICE_NAME"] = merged.get("SERVICE_NAME") or CONFIG.get("service_name", SCRIPT_NAME)
    merged["TURNSTILE_REQUIRED"] = merged.get("TURNSTILE_REQUIRED") or "false"
    merged["TURNSTILE_SITE_KEY"] = merged.get("TURNSTILE_SITE_KEY") or ""
    merged["TURNSTILE_SECRET_KEY"] = merged.get("TURNSTILE_SECRET_KEY") or ""
    merged["TURNSTILE_ALLOWED_HOSTNAMES"] = merged.get("TURNSTILE_ALLOWED_HOSTNAMES") or ""
    merged["WEB_CONCURRENCY"] = merged.get("WEB_CONCURRENCY") or "2"
    merged["GUNICORN_THREADS"] = merged.get("GUNICORN_THREADS") or "2"
    merged["GUNICORN_TIMEOUT"] = merged.get("GUNICORN_TIMEOUT") or "120"
    merged["SECRET_KEY"] = merged.get("SECRET_KEY") or "change-this-to-a-random-secret"
    merged["PUBLIC_BASE_URL"] = merged.get("PUBLIC_BASE_URL") or ""
    write_env_file(target, merged, "Generated by menuwed")
    return target


def update_env_keys(updates: dict[str, str]) -> None:
    ensure_env(force=False)
    current = read_env_file(env_path())
    for key, value in updates.items():
        current[key] = value
    write_env_file(env_path(), current, "Generated by menuwed")


def runtime_python() -> Path:
    py = venv_python()
    return py if py.exists() else Path(sys.executable)


def package_check() -> bool:
    python = runtime_python()
    code = "import flask, gunicorn, gdown, requests, dotenv, yt_dlp"
    proc = subprocess.run(
        [str(python), "-c", code],
        cwd=str(BASE_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.returncode == 0


def pip_install(args: list[str]) -> int:
    python = runtime_python()
    cmd = [str(python), "-m", "pip", *args]
    proc = subprocess.run(cmd, cwd=str(BASE_DIR))
    return proc.returncode


def create_venv() -> None:
    ensure_dirs()
    if venv_python().exists():
        return

    try:
        subprocess.run(
            [sys.executable, "-m", "venv", str(VENV_DIR)],
            cwd=str(BASE_DIR),
            check=True,
        )
    except subprocess.CalledProcessError:
        if os.name == "nt":
            raise
        if shutil.which("sudo") and shutil.which("apt-get"):
            subprocess.run(["sudo", "-n", "apt-get", "update"], capture_output=True)
            subprocess.run(
                ["sudo", "-n", "apt-get", "install", "-y", "python3-venv", "python3-pip"],
                capture_output=True,
            )
            subprocess.run(
                [sys.executable, "-m", "venv", str(VENV_DIR)],
                cwd=str(BASE_DIR),
                check=True,
            )
        else:
            raise

    if os.name != "nt":
        try:
            subprocess.run([str(venv_python()), "-m", "ensurepip", "--upgrade"], check=False)
        except Exception:
            pass


def ensure_dependencies(force: bool = False) -> None:
    create_venv()
    if force or not package_check():
        code = pip_install(["install", "--disable-pip-version-check", "--upgrade", "pip", "setuptools", "wheel"])
        if code != 0:
            raise RuntimeError("ไม่สามารถอัปเกรด pip ได้")
        req_code = pip_install(["install", "--disable-pip-version-check", "-r", str(REQUIREMENTS_PATH)])
        if req_code != 0:
            raise RuntimeError("ติดตั้งไลบรารี่ไม่สำเร็จ")
    if platform.system().lower() == "linux" and not shutil.which("ffmpeg"):
        if shutil.which("sudo") and shutil.which("apt-get"):
            subprocess.run(["sudo", "-n", "apt-get", "install", "-y", "ffmpeg"], capture_output=True)


def open_port_best_effort(port: int) -> str:
    port = int(port)
    if port <= 0:
        return "ไม่พบพอร์ตที่ต้องเปิด"

    system = platform.system().lower()

    if system == "windows":
        netsh = shutil.which("netsh")
        if not netsh:
            return "ไม่พบ netsh"
        cmd = [
            netsh,
            "advfirewall",
            "firewall",
            "add",
            "rule",
            f"name={SCRIPT_NAME}-{port}",
            "dir=in",
            "action=allow",
            "protocol=TCP",
            f"localport={port}",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return "เปิดพอร์ตแล้ว" if proc.returncode == 0 else "เปิดพอร์ตอัตโนมัติไม่สำเร็จ"

    if shutil.which("ufw"):
        cmd = ["ufw", "allow", f"{port}/tcp"]
        if os.geteuid() != 0 and shutil.which("sudo"):
            cmd = ["sudo", "-n", *cmd]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return "เปิดพอร์ตแล้ว" if proc.returncode == 0 else "เปิดพอร์ตอัตโนมัติไม่สำเร็จ"

    if shutil.which("firewall-cmd"):
        base = ["firewall-cmd", "--permanent", "--add-port", f"{port}/tcp"]
        if os.geteuid() != 0 and shutil.which("sudo"):
            base = ["sudo", "-n", *base]
        proc = subprocess.run(base, capture_output=True, text=True)
        if proc.returncode == 0:
            reload_cmd = ["firewall-cmd", "--reload"]
            if os.geteuid() != 0 and shutil.which("sudo"):
                reload_cmd = ["sudo", "-n", *reload_cmd]
            subprocess.run(reload_cmd, capture_output=True, text=True)
            return "เปิดพอร์ตแล้ว"
        return "เปิดพอร์ตอัตโนมัติไม่สำเร็จ"

    return "ไม่พบเครื่องมือเปิดพอร์ตอัตโนมัติ"


def prompt_yes_no(message: str) -> bool:
    answer = input(f"{message} (yes/no): ").strip().lower()
    return answer in {"y", "yes"}


def read_text(prompt: str, default: str = "") -> str:
    value = input(f"{prompt}{' [' + default + ']' if default else ''}: ").strip()
    return value or default


def view_env() -> None:
    env = read_env_file(env_path())
    all_keys = [
        "SECRET_KEY",
        "PROJECT_NAME",
        "APP_VERSION",
        "PUBLIC_BASE_URL",
        "DATA_DIR",
        "WEB_HOST",
        "WEB_PORT",
        "PORT",
        "SERVICE_NAME",
        "VENV_DIR",
        "TURNSTILE_SITE_KEY",
        "TURNSTILE_SECRET_KEY",
        "TURNSTILE_REQUIRED",
        "TURNSTILE_ALLOWED_HOSTNAMES",
        "WEB_CONCURRENCY",
        "GUNICORN_THREADS",
        "GUNICORN_TIMEOUT",
        "FLASK_ENV",
        "IS_PRODUCTION",
    ]
    print("\n=== .env ===")
    for key in all_keys:
        value = env.get(key, "")
        print(f'{key} = "{value}"')


def edit_env_interactively() -> None:
    ensure_env(force=False)
    env = read_env_file(env_path())
    keys = [
        "SECRET_KEY",
        "PROJECT_NAME",
        "APP_VERSION",
        "PUBLIC_BASE_URL",
        "DATA_DIR",
        "WEB_HOST",
        "WEB_PORT",
        "SERVICE_NAME",
        "VENV_DIR",
        "TURNSTILE_SITE_KEY",
        "TURNSTILE_SECRET_KEY",
        "TURNSTILE_REQUIRED",
        "TURNSTILE_ALLOWED_HOSTNAMES",
        "WEB_CONCURRENCY",
        "GUNICORN_THREADS",
        "GUNICORN_TIMEOUT",
    ]
    print("\nกรอกค่าใหม่หรือกด Enter เพื่อคงค่าเดิม")
    for key in keys:
        current = env.get(key, "")
        value = input(f"{key} [{current}]: ").strip()
        if value:
            env[key] = value

    env["PROJECT_NAME"] = env.get("PROJECT_NAME") or config_project_name()
    env["APP_VERSION"] = env.get("APP_VERSION") or config_app_version()
    env["DATA_DIR"] = env.get("DATA_DIR") or str(data_root())
    env["WEB_PORT"] = env.get("WEB_PORT") or env.get("PORT") or str(SYSTEM_PORT)
    env["PORT"] = env["WEB_PORT"]
    env["WEB_HOST"] = env.get("WEB_HOST") or SYSTEM_HOST
    env["SERVICE_NAME"] = env.get("SERVICE_NAME") or CONFIG.get("service_name", SCRIPT_NAME)
    env["VENV_DIR"] = env.get("VENV_DIR") or default_venv_dir()
    env["TURNSTILE_REQUIRED"] = env.get("TURNSTILE_REQUIRED") or "false"

    write_env_file(env_path(), env, "Generated by menuwed")
    print(f"บันทึก .env แล้ว: {env_path()}")


def open_env_in_editor() -> None:
    ensure_env(force=False)
    editor = os.getenv("EDITOR")
    if not editor:
        if os.name == "nt":
            editor = "notepad"
        elif shutil.which("nano"):
            editor = "nano"
        else:
            editor = "vi"
    subprocess.run([editor, str(env_path())], cwd=str(BASE_DIR))


def web_status() -> dict[str, str]:
    env = read_env_file(env_path())
    port = int(env.get("PORT") or env.get("WEB_PORT") or SYSTEM_PORT)
    pid = read_pid()
    pid_alive = bool(pid and is_process_alive(pid))
    endpoint_alive = check_local_web_ready(port)
    alive = pid_alive or endpoint_alive
    return {
        "pid": str(pid or "-"),
        "pid_alive": "yes" if pid_alive else "no",
        "endpoint_alive": "yes" if endpoint_alive else "no",
        "alive": "yes" if alive else "no",
        "url": public_url(),
        "port": str(port),
        "project": runtime_metadata(env_path())["project_name"],
        "version": runtime_metadata(env_path())["app_version"],
    }


def print_web_status() -> None:
    status = web_status()
    print("\n=== สถานะเว็บ ===")
    print(f"สถานะ: {'กำลังทำงาน' if status['alive'] == 'yes' else 'หยุดอยู่'}")
    print(f"PID: {status['pid']}")
    print(f"PID ยังทำงาน: {status['pid_alive']}")
    print(f"ตอบสนองพอร์ต: {status['endpoint_alive']}")
    print(f"URL: {status['url']}")
    print(f"พอร์ต: {status['port']}")
    print(f"โปรเจกต์: {status['project']}")
    print(f"เวอร์ชัน: {status['version']}")


def start_web_foreground() -> int:
    ensure_env(force=False)
    ensure_dependencies(force=True)
    env = current_env()
    env["PORT"] = env.get("PORT") or env.get("WEB_PORT") or str(SYSTEM_PORT)
    env["WEB_PORT"] = env["PORT"]
    env["WEB_HOST"] = env.get("WEB_HOST") or SYSTEM_HOST
    command = web_command()
    proc = subprocess.run(command, cwd=str(BASE_DIR), env=env)
    return proc.returncode


def start_web_background() -> int:
    ensure_env(force=False)
    ensure_dependencies(force=False)

    pid = read_pid()
    if pid and is_process_alive(pid):
        print(f"เว็บกำลังทำงานอยู่แล้ว (PID {pid})")
        return 0

    env = current_env()
    env["PORT"] = env.get("PORT") or env.get("WEB_PORT") or str(SYSTEM_PORT)
    env["WEB_PORT"] = env["PORT"]
    env["WEB_HOST"] = env.get("WEB_HOST") or SYSTEM_HOST

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_handle = open(WEB_LOG_FILE, "a", encoding="utf-8")

    creationflags = 0
    start_new_session = False
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        start_new_session = True

    command = web_command()
    proc = subprocess.Popen(
        command,
        cwd=str(BASE_DIR),
        env=env,
        stdout=log_handle,
        stderr=log_handle,
        stdin=subprocess.DEVNULL,
        start_new_session=start_new_session,
        creationflags=creationflags,
        close_fds=(os.name != "nt"),
    )
    write_pid(proc.pid)

    port = int(env.get("PORT") or env.get("WEB_PORT") or SYSTEM_PORT)
    started = False
    for _ in range(20):
        if proc.poll() is not None:
            break
        if check_local_web_ready(port, timeout=1.5):
            started = True
            break
        time.sleep(0.5)

    if proc.poll() is not None and not started:
        clear_pid()
        print(f"เริ่มเว็บไม่สำเร็จ (PID {proc.pid})")
        log_tail = tail_log_file(WEB_LOG_FILE)
        if log_tail:
            print("--- log ล่าสุด ---")
            print(log_tail)
        return 1

    if not started and check_local_web_ready(port, timeout=1.5):
        started = True

    print(f"เริ่มเว็บแล้ว (PID {proc.pid})")
    print(f"เปิดที่: {public_url()}")
    if not started:
        print("หมายเหตุ: กระบวนการเริ่มแล้ว แต่ยังตอบสนองช้าอยู่เล็กน้อย")
    return 0


def stop_web() -> int:
    pid = read_pid()
    if not pid or not is_process_alive(pid):
        clear_pid()
        print("เว็บไม่ได้ทำงาน")
        return 0

    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass
        for _ in range(10):
            if not is_process_alive(pid):
                break
            time.sleep(0.5)
        if is_process_alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass

    clear_pid()
    print("หยุดเว็บแล้ว")
    return 0


def restart_web() -> int:
    stop_web()
    return start_web_background()


def show_web_info() -> None:
    meta = runtime_metadata(env_path())
    print("\n=== ข้อมูลเว็บ ===")
    print(f"ชื่อโปรเจกต์: {meta['project_name']}")
    print(f"เวอร์ชัน: {meta['app_version']}")
    print(f"ที่ตั้งไฟล์: {INSTALL_PATH}")
    print(f"โฟลเดอร์ข้อมูล: {data_root()}")
    print(f"พอร์ตเว็บ: {read_env_file(env_path()).get('WEB_PORT') or read_env_file(env_path()).get('PORT') or SYSTEM_PORT}")
    print(f"URL เข้าชม: {public_url()}")
    print(f"ไฟล์ .env: {env_path()}")
    print(f"Virtualenv: {VENV_DIR}")
    print(f"PID file: {PID_FILE}")


def bind_domain() -> None:
    current = read_env_file(env_path()).get("PUBLIC_BASE_URL", "")
    value = read_text("ใส่โดเมนหรือ URL เต็ม", current)
    if value and "://" not in value and "." in value:
        value = f"https://{value.strip('/')}"
    update_env_keys({"PUBLIC_BASE_URL": value})
    print(f"ผูกโดเมนแล้ว: {value or '(ล้างค่า)'}")


def web_menu() -> int:
    while True:
        print("\n=== จัดการเว็บ ===")
        print("1) ดู URL และอื่นๆ")
        print("2) ผูกโดเมน")
        print("3) ดูสถานะการทำงานเว็บ")
        print("4) รีสตาร์ทเว็บ")
        print("5) หยุดเว็บไซต์")
        print("6) เริ่มเว็บไซต์")
        print("0) กลับ")
        choice = input("เลือก: ").strip()

        if choice == "1":
            show_web_info()
        elif choice == "2":
            bind_domain()
        elif choice == "3":
            print_web_status()
        elif choice == "4":
            restart_web()
        elif choice == "5":
            stop_web()
        elif choice == "6":
            start_web_background()
        elif choice == "0":
            return 0
        else:
            print("เลือกไม่ถูกต้อง")


def env_menu() -> int:
    while True:
        print("\n=== จัดการ .env ===")
        print("1) ดูค่าปัจจุบันทั้งหมด")
        print("2) สร้าง/ซ่อม .env")
        print("3) แก้ค่าแบบถามทีละตัว")
        print("4) เปิดไฟล์ .env ใน editor")
        print("0) กลับ")
        choice = input("เลือก: ").strip()

        if choice == "1":
            view_env()
        elif choice == "2":
            ensure_env(force=True)
            print(f"สร้าง/ซ่อม .env แล้ว: {env_path()}")
        elif choice == "3":
            edit_env_interactively()
        elif choice == "4":
            open_env_in_editor()
        elif choice == "0":
            return 0
        else:
            print("เลือกไม่ถูกต้อง")


def uninstall(confirm: bool = True) -> int:
    if confirm:
        if not prompt_yes_no("ต้องการถอนการติดตั้งหรือไม่"):
            return 0
        if not prompt_yes_no("ยืนยันอีกครั้งว่าต้องการลบทั้งหมด"):
            return 0

    stop_web()
    install_dir = INSTALL_PATH
    data_dir = data_root()

    if install_dir.exists():
        shutil.rmtree(install_dir, ignore_errors=True)
    if data_dir.exists() and data_dir != install_dir:
        shutil.rmtree(data_dir, ignore_errors=True)

    print("ถอนการติดตั้งเสร็จแล้ว")
    return 0


def _extract_release_zip(zip_path: Path, target_dir: Path) -> Path:
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(target_dir)
    dirs = [p for p in target_dir.iterdir() if p.is_dir()]
    if not dirs:
        raise RuntimeError("แตกไฟล์ release ไม่สำเร็จ")
    return dirs[0]


def _download_file(url: str, out_path: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "menuwed"})
    with urllib.request.urlopen(req, timeout=60) as resp, out_path.open("wb") as fh:
        shutil.copyfileobj(resp, fh)


def _copy_release_tree(source_root: Path, destination: Path) -> None:
    preserve = {
        default_env_file_name(),
        ".menuwed-installed",
        ".menuwed-web.pid",
        "logs",
        default_venv_dir(),
        "__pycache__",
        ".git",
        "menuwed_config.json",
    }
    for item in source_root.iterdir():
        if item.name in preserve:
            continue
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


def _perform_update(zip_url: str, label: str) -> int:
    if not zip_url:
        print("ไม่พบ release ที่ต้องการอัปเดต")
        return 1

    ensure_dirs()
    with tempfile.TemporaryDirectory(prefix="menuwed_update_") as td:
        tmp = Path(td)
        zip_path = tmp / "release.zip"
        extract_dir = tmp / "extract"
        extract_dir.mkdir(parents=True, exist_ok=True)

        print(f"กำลังดาวน์โหลด {label}...")
        _download_file(zip_url, zip_path)
        print("กำลังแตกไฟล์...")
        src_root = _extract_release_zip(zip_path, extract_dir)

        print("กำลังแทนที่ไฟล์โปรเจกต์...")
        _copy_release_tree(src_root, INSTALL_PATH)

    ensure_env(force=False)
    ensure_dependencies(force=False)
    print("อัปเดตเสร็จแล้ว")
    print(f"เวอร์ชันปัจจุบัน: {runtime_metadata(env_path())['app_version']}")
    return 0


def update_latest() -> int:
    info = latest_release_info(github_repo())
    version = info.get("tag_name") or "latest"
    return _perform_update(info["zipball_url"], f"release ล่าสุด ({version})")


def update_specific() -> int:
    value = read_text("ใส่ release tag หรือ URL zipball")
    if not value:
        print("ยกเลิก")
        return 0
    if value.startswith(("http://", "https://")):
        return _perform_update(value, "release ที่ระบุ")
    info = latest_release_info(github_repo(), value)
    version = info.get("tag_name") or value
    return _perform_update(info["zipball_url"], f"release tag ({version})")


def update_libraries() -> int:
    ensure_dependencies(force=True)
    print("อัปเดตไลบรารี่เสร็จแล้ว")
    return 0


def install() -> int:
    if MARKER_FILE.exists():
        print(f"พบการติดตั้งอยู่แล้วที่ {INSTALL_PATH}")
        print("ถ้าจะติดตั้งใหม่ ต้องถอนการติดตั้งตัวเก่าออกก่อน")
        return 1

    ensure_dirs()
    ensure_env(force=False)
    ensure_dependencies(force=False)
    port = int(read_env_file(env_path()).get("PORT") or read_env_file(env_path()).get("WEB_PORT") or SYSTEM_PORT)
    result = open_port_best_effort(port)
    MARKER_FILE.write_text("installed\n", encoding="utf-8")

    meta = runtime_metadata(env_path())
    print(f"ติดตั้งพร้อมใช้งาน: {INSTALL_PATH}")
    print(f"คำสั่งหลัก: {INSTALL_PATH / SCRIPT_NAME}")
    print(f"โปรเจกต์: {meta['project_name']}")
    print(f"เวอร์ชัน (tag ล่าสุด): {meta['app_version']}")
    print(f"พอร์ต: {port}")
    print(f"เปิดพอร์ตอัตโนมัติ: {result}")
    print(f"ช่องทาง release: {RELEASE_CHANNEL}")
    print(f"เรียกใช้งานได้ทันที: {SCRIPT_NAME}")
    print(f"ติดตั้งเสร็จ: {INSTALL_PATH}")
    return 0


def status() -> int:
    print_web_status()
    return 0


def interactive_menu() -> int:
    while True:
        if is_remote_mode() and not sys.stdin.isatty():
            return start_web_foreground()

        meta = runtime_metadata(env_path())
        print("\n=== menuwed ===")
        print(f"โปรเจกต์: {meta['project_name']}")
        print(f"เวอร์ชัน: {meta['app_version']}")
        print(f"ที่ตั้ง: {INSTALL_PATH}")
        print("1) ถอนการติดตั้ง")
        print("2) อัปเดตระบบ")
        print("3) อัปเดตแบบเจาะจง")
        print("4) อัปเดตไลบารี่")
        print("5) จัดการเว็บ")
        print("6) จัดการ .env")
        print("0) ออกเมนู")
        choice = input("เลือก: ").strip()

        if choice == "1":
            return uninstall(confirm=True)
        if choice == "2":
            return update_latest()
        if choice == "3":
            return update_specific()
        if choice == "4":
            return update_libraries()
        if choice == "5":
            web_menu()
        elif choice == "6":
            env_menu()
        elif choice == "0":
            return 0
        else:
            print("เลือกไม่ถูกต้อง")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=SCRIPT_NAME, add_help=True)
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("install", help="ติดตั้ง/เตรียมสภาพแวดล้อม")
    sub.add_parser("start", help="เริ่มเว็บแบบ foreground")
    sub.add_parser("web-start", help="เริ่มเว็บแบบ background")
    sub.add_parser("web-stop", help="หยุดเว็บ")
    sub.add_parser("web-status", help="ดูสถานะเว็บ")
    sub.add_parser("web-restart", help="รีสตาร์ทเว็บ")
    sub.add_parser("env", help="สร้าง/ซ่อม .env")
    sub.add_parser("status", help="ดูสถานะโดยรวม")
    sub.add_parser("update", help="อัปเดตระบบจาก release ล่าสุด")
    sub.add_parser("update-libs", help="อัปเดตไลบรารี่")
    sub.add_parser("uninstall", help="ถอนการติดตั้ง")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        argv = list(sys.argv[1:] if argv is None else argv)
        parser = build_parser()
        args = parser.parse_args(argv)

        if args.command == "install":
            return install()
        if args.command == "start":
            return start_web_foreground()
        if args.command == "web-start":
            return start_web_background()
        if args.command == "web-stop":
            return stop_web()
        if args.command == "web-status":
            return status()
        if args.command == "web-restart":
            return restart_web()
        if args.command == "env":
            return env_menu()
        if args.command == "status":
            return status()
        if args.command == "update":
            return update_latest()
        if args.command == "update-libs":
            return update_libraries()
        if args.command == "uninstall":
            return uninstall(confirm=True)

        return interactive_menu()
    except KeyboardInterrupt:
        print("\nยกเลิก")
        return 130
    except Exception as exc:
        if os.getenv("MENUWED_DEBUG"):
            raise
        print(f"เกิดข้อผิดพลาด: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
