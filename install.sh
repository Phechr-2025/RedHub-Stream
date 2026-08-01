#!/usr/bin/env sh
set -eu

DEFAULT_REPO="Phechr-2025/RedHub-Stream"
DEFAULT_PROJECT_NAME="MySeriesVideo"
DEFAULT_VERSION="latest"
DEFAULT_INSTALL_PATH_UNIX="~/menuwed"
DEFAULT_DATA_DIR_UNIX="~/menuwed-data"
DEFAULT_SERVICE_NAME="menuwed"
DEFAULT_ENV_FILE=".env"
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

echo "กำลังดาวน์โหลด release ล่าสุด (${VERSION_TAG})..."
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

echo "$ZIP_PATH"
echo "กำลังแตกไฟล์..."
python3 - "$ZIP_PATH" "$TMPDIR/extract" <<'PY'
import sys, zipfile, pathlib
zip_path = pathlib.Path(sys.argv[1])
extract_path = pathlib.Path(sys.argv[2])
extract_path.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(zip_path) as z:
    z.extractall(extract_path)
print("ok")
PY

TOP_DIR="$(find "$TMPDIR/extract" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
if [ -z "$TOP_DIR" ]; then
  echo "แตกไฟล์ไม่สำเร็จ"
  exit 1
fi

mkdir -p "$INSTALL_PATH"
cp -a "$TOP_DIR"/. "$INSTALL_PATH"/

mkdir -p "$DATA_DIR"

cd "$INSTALL_PATH"
chmod +x menuwed menuwed.py start.sh install.sh 2>/dev/null || true

PROJECT_NAME="$PROJECT_NAME_RAW" APP_VERSION="$VERSION_TAG" DATA_DIR="$DATA_DIR" python3 menuwed.py install

mkdir -p "$HOME/.local/bin"
ln -sf "$INSTALL_PATH/menuwed" "$HOME/.local/bin/menuwed" 2>/dev/null || true

if command -v sudo >/dev/null 2>&1; then
  sudo ln -sf "$INSTALL_PATH/menuwed" /usr/local/bin/menuwed 2>/dev/null || true
fi

echo "โปรเจกต์: $PROJECT_NAME_RAW"
echo "เวอร์ชัน (tag ล่าสุด): $VERSION_TAG"
echo "ช่องทาง release: $RELEASE_CHANNEL_RAW"
echo "ติดตั้งพร้อมใช้งาน: $INSTALL_PATH"
echo "คำสั่งหลัก: $INSTALL_PATH/menuwed"
if command -v menuwed >/dev/null 2>&1; then
  echo "เรียกใช้งานได้ทันที: menuwed"
else
  echo "ถ้า shell ยังหาไม่เจอ ให้เพิ่ม $HOME/.local/bin ลง PATH"
fi
echo "ติดตั้งเสร็จ: $INSTALL_PATH"
