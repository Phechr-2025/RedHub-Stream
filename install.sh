#!/usr/bin/env sh
set -eu

DEFAULT_REPO="Phechr-2025/RedHub-Stream"
DEFAULT_PROJECT_NAME="MySeriesVideo"
DEFAULT_VERSION="latest"
DEFAULT_INSTALL_PATH_UNIX="~/menuwed"
DEFAULT_DATA_DIR_UNIX="~/menuwed-data"
DEFAULT_SERVICE_NAME="menuwed"
DEFAULT_RELEASE_CHANNEL="latest"

CONFIG_URL="https://raw.githubusercontent.com/${DEFAULT_REPO}/main/menuwed_config.json"

json_get() {
python3 - "$1" "$2" <<'PY'
import json, sys
obj = json.loads(sys.argv[1] or "{}")
key = sys.argv[2]
value = obj.get(key, "")
if value is None:
    value = ""
print(value)
PY
}

fetch_config_json() {
python3 - "$CONFIG_URL" <<'PY'
import json, sys, urllib.request
url = sys.argv[1]
try:
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    print(json.dumps(data, ensure_ascii=False))
except Exception:
    print("{}")
PY
}

expand_path() {
python3 - "$1" <<'PY'
import os, sys, pathlib
value = sys.argv[1].replace("%USERPROFILE%", str(pathlib.Path.home()))
print(os.path.expandvars(os.path.expanduser(value)))
PY
}

ensure_venv_support() {
  if python3 -m venv "$TMPDIR/venv-check" >/dev/null 2>&1; then
    rm -rf "$TMPDIR/venv-check" >/dev/null 2>&1 || true
    return 0
  fi

  if command -v sudo >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
    if sudo -n apt-get update >/dev/null 2>&1; then
      sudo -n apt-get install -y python3-venv python3-pip >/dev/null 2>&1 || true
      if command -v ffmpeg >/dev/null 2>&1; then
        :
      else
        sudo -n apt-get install -y ffmpeg >/dev/null 2>&1 || true
      fi
      if python3 -m venv "$TMPDIR/venv-check" >/dev/null 2>&1; then
        rm -rf "$TMPDIR/venv-check" >/dev/null 2>&1 || true
        return 0
      fi
    fi
  fi

  echo "ต้องมี python3-venv ก่อน หากสคริปต์ติดตั้งอัตโนมัติไม่ได้ ให้ติดตั้งเองด้วย sudo apt-get install -y python3-venv python3-pip"
  exit 1
}

CONFIG_JSON="$(fetch_config_json)"

PROJECT_NAME_RAW="$(json_get "$CONFIG_JSON" project_name)"
[ -n "$PROJECT_NAME_RAW" ] || PROJECT_NAME_RAW="$DEFAULT_PROJECT_NAME"

VERSION_RAW="$(json_get "$CONFIG_JSON" version)"
[ -n "$VERSION_RAW" ] || VERSION_RAW="$DEFAULT_VERSION"

INSTALL_PATH_RAW="$(json_get "$CONFIG_JSON" install_path_unix)"
[ -n "$INSTALL_PATH_RAW" ] || INSTALL_PATH_RAW="$DEFAULT_INSTALL_PATH_UNIX"

DATA_DIR_RAW="$(json_get "$CONFIG_JSON" data_dir_unix)"
[ -n "$DATA_DIR_RAW" ] || DATA_DIR_RAW="$DEFAULT_DATA_DIR_UNIX"

SERVICE_NAME_RAW="$(json_get "$CONFIG_JSON" service_name)"
[ -n "$SERVICE_NAME_RAW" ] || SERVICE_NAME_RAW="$DEFAULT_SERVICE_NAME"

ENV_FILE_RAW="$(json_get "$CONFIG_JSON" env_file)"
[ -n "$ENV_FILE_RAW" ] || ENV_FILE_RAW="$DEFAULT_ENV_FILE"

RELEASE_CHANNEL_RAW="$(json_get "$CONFIG_JSON" release_channel)"
[ -n "$RELEASE_CHANNEL_RAW" ] || RELEASE_CHANNEL_RAW="$DEFAULT_RELEASE_CHANNEL"

REPO_RAW="$(json_get "$CONFIG_JSON" github_repo)"
[ -n "$REPO_RAW" ] || REPO_RAW="$DEFAULT_REPO"

INSTALL_PATH="$(expand_path "$INSTALL_PATH_RAW")"
DATA_DIR="$(expand_path "$DATA_DIR_RAW")"

TMPDIR="$(mktemp -d)"
cleanup() { rm -rf "$TMPDIR"; }
trap cleanup EXIT

RELEASE_INFO_JSON="$(python3 - "$REPO_RAW" <<'PY'
import json, sys, urllib.request
repo = sys.argv[1]
api = f"https://api.github.com/repos/{repo}/releases/latest"
req = urllib.request.Request(api, headers={"User-Agent": "menuwed"})
with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.loads(resp.read().decode("utf-8"))
print(json.dumps(data, ensure_ascii=False))
PY
)"

VERSION_TAG="$(json_get "$RELEASE_INFO_JSON" tag_name)"
[ -n "$VERSION_TAG" ] || VERSION_TAG="$VERSION_RAW"

ZIP_URL="$(json_get "$RELEASE_INFO_JSON" zipball_url)"
if [ -z "$ZIP_URL" ]; then
  echo "ไม่พบ zipball_url ของ release ล่าสุด"
  exit 1
fi

if [ -e "$INSTALL_PATH/.menuwed-installed" ]; then
  echo "พบการติดตั้งอยู่แล้วที่ $INSTALL_PATH"
  echo "หากต้องการติดตั้งใหม่ให้ถอนการติดตั้งก่อน"
  exit 1
fi

ensure_venv_support

echo "กำลังดาวน์โหลด release ล่าสุด เวอร์ชั่น ${VERSION_TAG}..."
ZIP_PATH="$TMPDIR/release.zip"

if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$ZIP_URL" -o "$ZIP_PATH"
else
  python3 - "$ZIP_URL" "$ZIP_PATH" <<'PY'
import sys, urllib.request
url, out = sys.argv[1], sys.argv[2]
urllib.request.urlretrieve(url, out)
PY
fi

echo "กำลังแตกไฟล์..."
python3 - "$ZIP_PATH" "$TMPDIR/extract" <<'PY'
import sys, zipfile, pathlib
zip_path = pathlib.Path(sys.argv[1])
extract_path = pathlib.Path(sys.argv[2])
extract_path.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(zip_path) as z:
    z.extractall(extract_path)
PY

TOP_DIR="$(find "$TMPDIR/extract" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
if [ -z "$TOP_DIR" ]; then
  echo "แตกไฟล์ไม่สำเร็จ"
  exit 1
fi

echo "กำลังเริ่มติดตั้ง..."

mkdir -p "$INSTALL_PATH"
cp -a "$TOP_DIR"/. "$INSTALL_PATH"/

mkdir -p "$DATA_DIR"

cd "$INSTALL_PATH"
chmod +x menuwed menuwed.py start.sh install.sh 2>/dev/null || true

INSTALL_LOG="$TMPDIR/install.log"
if command -v tee >/dev/null 2>&1; then
  PROJECT_NAME="$PROJECT_NAME_RAW" APP_VERSION="$VERSION_TAG" DATA_DIR="$DATA_DIR" python3 menuwed.py install 2>&1 | tee "$INSTALL_LOG"
else
  PROJECT_NAME="$PROJECT_NAME_RAW" APP_VERSION="$VERSION_TAG" DATA_DIR="$DATA_DIR" python3 menuwed.py install > "$INSTALL_LOG" 2>&1
  cat "$INSTALL_LOG"
fi

FIREWALL_RESULT="$(python3 - "$INSTALL_LOG" <<'PY'
import pathlib
import re
import sys

log_path = pathlib.Path(sys.argv[1])
result = ""
if log_path.exists():
    for line in reversed(log_path.read_text(encoding="utf-8", errors="replace").splitlines()):
        if "เตรียมติดตั้งเสร็จแล้ว:" not in line:
            continue
        match = re.search(r"\(([^()]*)\)\s*$", line)
        if match:
            result = match.group(1).strip()
            break
print(result)
PY
)"

mkdir -p "$HOME/.local/bin"
ln -sf "$INSTALL_PATH/menuwed" "$HOME/.local/bin/menuwed" 2>/dev/null || true

if command -v sudo >/dev/null 2>&1; then
  sudo ln -sf "$INSTALL_PATH/menuwed" /usr/local/bin/menuwed 2>/dev/null || true
fi

if command -v menuwed >/dev/null 2>&1; then
  menuwed web-start || true
else
  python3 "$INSTALL_PATH/menuwed.py" web-start || true
fi
sleep 2
if command -v menuwed >/dev/null 2>&1; then
  menuwed web-status || true
else
  python3 "$INSTALL_PATH/menuwed.py" web-status || true
fi

python3 - "$INSTALL_PATH" "$PROJECT_NAME_RAW" "$VERSION_TAG" "$FIREWALL_RESULT" <<'PY'
import pathlib
import socket
import sys

install_path = pathlib.Path(sys.argv[1])
project_name = sys.argv[2]
version = sys.argv[3]
firewall_result = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4].strip() else "ไม่ทราบ"

def read_env_file(path: pathlib.Path) -> dict[str, str]:
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

def private_ip() -> str:
    host = local_ip() or "127.0.0.1"
    try:
        octets = [int(part) for part in host.split(".")]
        if len(octets) == 4:
            a, b, c, d = octets
            if a == 10 or (a == 192 and b == 168) or (a == 172 and 16 <= b <= 31):
                return host
    except Exception:
        pass
    return "127.0.0.1"

env = read_env_file(install_path / "menuwed_config.json")
port = int(env.get("PORT") or env.get("WEB_PORT") or "5000")
pid_path = install_path / ".menuwed-web.pid"
pid = pid_path.read_text(encoding="utf-8").strip() if pid_path.exists() else "-"
status = "กำลังทำงาน" if pid != "-" else "ไม่พบการทำงาน"
private_url = f"http://{private_ip()}:{port}"
public_url = env.get("PUBLIC_BASE_URL") or f"http://127.0.0.1:{port}"

title = f"{project_name} v{version}"
width = max(30, len(title) + 8)
line = "═" * width

print(line)
print(title.center(width))
print(line)
print()
print(f"📦 โปรเจกต์ : {project_name}")
print(f"🏷️ เวอร์ชัน : {version}")
print(f"📂 ติดตั้ง : {install_path}")
print(f"⚙️ คำสั่ง : {install_path / 'menuwed'}")
print(f"🌐 พอร์ต : {port}")
print(f"🔥 Firewall : {firewall_result}")
print()
print("✅ เว็บเริ่มทำงานเรียบร้อย")
print(f"🟢 สถานะ : {status}")
print(f"🆔 PID : {pid}")
print()
print("🔗 Private URL")
print(private_url)
print()
print("🔗 Public URL")
print(public_url)
print()
print("เรียกใช้งานเมนู : menuwed")
print(line)
PY
