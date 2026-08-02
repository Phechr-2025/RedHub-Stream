# MySeriesVideo / menuwed

โปรเจกต์นี้เป็นเว็บดูวิดีโอแบบ Flask พร้อมตัวจัดการติดตั้ง/อัปเดต/เว็บ/config ชื่อ `menuwed`

## สิ่งที่ปรับในรอบนี้

- รองรับอุปกรณ์หลายขนาดมากขึ้น ทั้งมือถือ แท็บเล็ต และเดสก์ท็อป
- โหลดวิดีโอและเสียงได้ด้วย player ที่ responsive
- ติดตั้งไลบรารีและ runtime อัตโนมัติผ่าน virtualenv
- รองรับ Ubuntu / Debian / Windows ด้วยคำสั่งติดตั้งเดียวต่อระบบ
- คำสั่ง `menuwed` ใช้งานได้ทันทีหลังติดตั้ง
- เพิ่มเมนูจัดการเว็บ, อัปเดตระบบ, อัปเดตแบบเจาะจง, อัปเดตไลบรารี, และจัดการ config
- เพิ่มโหมดไม่มีเมนูสำหรับ environment แบบ Render / cloud
- ผูกโดเมนแล้วจะพยายามตั้งค่า nginx reverse proxy บน 80/443 ให้โดยอัตโนมัติเมื่อมีสิทธิ์ sudo
- ป้องกันการติดตั้งซ้ำ ถ้ามีอยู่แล้วต้องถอนก่อน
- เก็บค่าปรับแต่งหลักไว้ที่ `menuwed_config.json` แก้ไฟล์เดียวมีผล

## แก้ไฟล์ไหนได้บ้าง

จุดสำคัญอยู่ที่ไฟล์เหล่านี้:

- `menuwed_config.json` — แก้ชื่อโปรเจกต์, path, port, repo, version fallback
- `menuwed.py` — ตัวเมนูหลัก, install/update/web/config
- `install.sh` — ติดตั้งบน Ubuntu / Debian
- `install.ps1` — ติดตั้งบน Windows
- `app.py` — เว็บหลัก
- `templates/` + `static/style.css` — หน้าจอ responsive และ media player
- `menuwed_config.json` — ไฟล์ config หลักของระบบ

## วิธีติดตั้ง

### Ubuntu / Debian

```bash
curl -fsSL https://raw.githubusercontent.com/Phechr-2025/RedHub-Stream/main/install.sh | bash
```

### Windows (PowerShell)

```powershell
iwr https://raw.githubusercontent.com/Phechr-2025/RedHub-Stream/main/install.ps1 -UseBasicParsing | iex
```

## ใช้งาน

หลังติดตั้งแล้วพิมพ์:

```bash
menuwed
```

หรือบน Windows:

```powershell
menuwed
```

## เมนูหลัก

1. ถอนการติดตั้ง  
2. อัปเดตระบบ  
3. อัปเดตแบบเจาะจง  
4. อัปเดตไลบรารี  
5. จัดการเว็บ  
6. จัดการ config  
0. ออกเมนู  

### จัดการเว็บ

- ดู URL และข้อมูลการรัน
- ผูกโดเมน
- ดูสถานะเว็บ
- รีสตาร์ทเว็บ
- หยุดเว็บ
- เริ่มเว็บ

### จัดการ config

- ดูค่าปัจจุบันทั้งหมด
- สร้าง/ซ่อมไฟล์ config
- แก้ค่าแบบถามทีละตัว
- เปิดไฟล์ config ใน editor

## การอัปเดต

- อัปเดตระบบ: ดึง release ล่าสุด
- อัปเดตแบบเจาะจง: ใส่ tag หรือ release URL ได้
- อัปเดตไลบรารี: ติดตั้ง dependency ล่าสุดเข้า venv เดิม

## หมายเหตุเรื่อง Turnstile

ตอนนี้ค่าเริ่มต้นเป็นแบบ **ไม่บังคับ** เพื่อให้ local / Render / cloud รันได้ทันที  
ถ้าต้องการบังคับใช้ ให้ตั้ง `TURNSTILE_REQUIRED=true` และใส่คีย์ให้ครบใน config

## หมายเหตุเรื่อง Render

ถ้ารันบน Render / environment คลาวด์ เมนู CLI จะไม่เด้งแบบ interactive ในโหมดไม่มี TTY และเว็บจะรันตรง ๆ แทน  
ไฟล์ `start.sh` ยังรองรับกรณีที่ไม่มี `gunicorn` ด้วยการ fallback ไป `python3 app.py`

## หมายเหตุเรื่องโดเมน / Cloudflare

เมื่อผูกโดเมนแล้ว ระบบจะพยายามสร้าง reverse proxy ด้วย nginx ไปยังพอร์ตภายในของแอป และจะเปิดพอร์ต 80/443 แบบ best-effort ถ้ามี sudo  
ตอนนี้ตัวจัดการโดเมนมี path สำหรับ nginx/certificate ครบแล้ว จึงไม่ควรเจอ `NameError: NGINX_SSL_DIR` ตอนผูกโดเมนอีก  
ถ้า Cloudflare ยังขึ้น 522 หลังผูกโดเมน ให้ตรวจว่า

- origin server ตอบได้จริงที่ `http://127.0.0.1:5000/healthz`
- nginx ทำงานและมี site ของโปรเจกต์ถูก enable แล้ว
- Lightsail / cloud firewall เปิด 80 และ 443
- Cloudflare ชี้ A record ไปยัง public IP ที่ถูกต้อง

## ไฟล์ config กลาง

แก้ที่ `menuwed_config.json` ไฟล์เดียวได้ เช่น:

- `project_name`
- `install_path_unix` / `install_path_windows`
- `data_dir_unix` / `data_dir_windows`
- `web_port`
- `github_repo`
- `version` fallback

ถ้าต้องการเปลี่ยนชื่อสคริปต์หรือ path ให้แก้ไฟล์นี้เป็นหลัก
