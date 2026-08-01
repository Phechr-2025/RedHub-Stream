param()

$DefaultRepo = "Phechr-2025/RedHub-Stream"
$DefaultProjectName = "MySeriesVideo"
$DefaultVersion = "latest"
$DefaultInstallPathWindows = "%USERPROFILE%\menuwed"
$DefaultDataDirWindows = "%USERPROFILE%\menuwed-data"
$DefaultServiceName = "menuwed"
$DefaultReleaseChannel = "latest"

$ConfigUrl = "https://raw.githubusercontent.com/$DefaultRepo/main/menuwed_config.json"
$Headers = @{ "User-Agent" = "menuwed" }

function Get-RemoteConfig {
  try {
    Invoke-RestMethod -Uri $ConfigUrl -Headers $Headers -ErrorAction Stop
  } catch {
    $null
  }
}

function Get-LatestReleaseInfo([string]$Repo) {
  try {
    $api = "https://api.github.com/repos/$Repo/releases/latest"
    Invoke-RestMethod -Uri $api -Headers $Headers -ErrorAction Stop
  } catch {
    $null
  }
}

function Get-ConfigValue([object]$Cfg, [string]$Name, [string]$DefaultValue) {
  if ($null -eq $Cfg) { return $DefaultValue }
  $prop = $Cfg.PSObject.Properties[$Name]
  if ($null -eq $prop) { return $DefaultValue }
  $value = [string]$prop.Value
  if ([string]::IsNullOrWhiteSpace($value)) { return $DefaultValue }
  $value
}

function Expand-PathValue([string]$Value) {
  $expanded = [Environment]::ExpandEnvironmentVariables($Value)
  [System.IO.Path]::GetFullPath($expanded)
}

$cfg = Get-RemoteConfig

$repo = Get-ConfigValue $cfg "github_repo" $DefaultRepo
$installPathRaw = Get-ConfigValue $cfg "install_path_windows" $DefaultInstallPathWindows
$dataDirRaw = Get-ConfigValue $cfg "data_dir_windows" $DefaultDataDirWindows
$serviceName = Get-ConfigValue $cfg "service_name" $DefaultServiceName
$projectName = Get-ConfigValue $cfg "project_name" $DefaultProjectName
$releaseChannel = Get-ConfigValue $cfg "release_channel" $DefaultReleaseChannel

$release = Get-LatestReleaseInfo $repo
if (-not $release) { throw "ไม่สามารถดึง release ล่าสุดได้" }

$version = if ($release.tag_name) { [string]$release.tag_name } else { Get-ConfigValue $cfg "version" $DefaultVersion }
$installPath = Expand-PathValue $installPathRaw
$dataDir = Expand-PathValue $dataDirRaw
$marker = Join-Path $installPath '.menuwed-installed'

if (Test-Path $marker) {
  throw "พบการติดตั้งอยู่แล้วที่ $installPath ต้องถอนการติดตั้งก่อน"
}

$tmpPath = [IO.Path]::Combine([IO.Path]::GetTempPath(), "menuwed-" + [guid]::NewGuid().ToString())
$tmp = New-Item -ItemType Directory -Force -Path $tmpPath

try {
  $zipUrl = $release.zipball_url
  if ([string]::IsNullOrWhiteSpace($zipUrl)) { throw "ไม่พบ zipball_url ใน release ล่าสุด" }

  $zipPath = Join-Path $tmp.FullName 'release.zip'
  Write-Host "กำลังดาวน์โหลด release ล่าสุด เวอร์ชั่น $version..."
  Invoke-WebRequest -Uri $zipUrl -Headers $Headers -OutFile $zipPath -ErrorAction Stop
  Write-Host "กำลังแตกไฟล์..."
  Expand-Archive -Path $zipPath -DestinationPath (Join-Path $tmp.FullName 'extract') -Force
  Write-Host "กำลังเริ่มติดตั้ง..."

  $topDir = Get-ChildItem (Join-Path $tmp.FullName 'extract') | Where-Object { $_.PSIsContainer } | Select-Object -First 1
  if (-not $topDir) { throw "แตกไฟล์ไม่สำเร็จ" }

  New-Item -ItemType Directory -Force -Path $installPath | Out-Null
  Copy-Item -Path (Join-Path $topDir.FullName '*') -Destination $installPath -Recurse -Force
  New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

  Set-Location $installPath
  $env:PROJECT_NAME = $projectName
  $env:APP_VERSION = $version
  $env:DATA_DIR = $dataDir
  py -3 menuwed.py install

  New-Item -ItemType File -Force -Path $marker | Out-Null

  $binDir = Join-Path $env:LOCALAPPDATA 'menuwed-bin'
  New-Item -ItemType Directory -Force -Path $binDir | Out-Null

  $cmdShim = Join-Path $binDir 'menuwed.cmd'
  @"
@echo off
py -3 "$installPath\menuwed.py" %*
"@ | Set-Content -Encoding ASCII $cmdShim

  $psShim = Join-Path $binDir 'menuwed.ps1'
  @"
param()
py -3 "$installPath\menuwed.py" @args
"@ | Set-Content -Encoding UTF8 $psShim

  $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
  if ([string]::IsNullOrWhiteSpace($userPath)) {
    [Environment]::SetEnvironmentVariable('Path', $binDir, 'User')
  } elseif ($userPath -notlike "*$binDir*") {
    [Environment]::SetEnvironmentVariable('Path', "$userPath;$binDir", 'User')
  }

  Write-Host "ติดตั้งเสร็จ: $installPath"
}
finally {
  if (Test-Path $tmp.FullName) {
    Remove-Item -Recurse -Force $tmp.FullName -ErrorAction SilentlyContinue
  }
}
