param(
    [string]$AppName = "",
    [string]$ShortcutName = "",
    [string]$VersionStamp = ""
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Resolve-Python {
    $candidates = @("py", "python")
    foreach ($candidate in $candidates) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command) {
            return $command.Source
        }
    }
    throw "Cannot find Python. Please install Python 3.10 or later and add it to PATH."
}

function New-UnicodeString {
    param([int[]]$CodePoints)

    return [string]::Concat(($CodePoints | ForEach-Object { [char]$_ }))
}

$defaultAppName = "TesterToolBox"
if (-not $AppName) {
    $AppName = $defaultAppName
}
if (-not $ShortcutName) {
    $ShortcutName = $defaultAppName
}
if (-not $VersionStamp) {
    $VersionStamp = Get-Date -Format "yyyyMMdd-HHmmss"
}
$shortcutDescription = (New-UnicodeString @(0x6253, 0x5F00)) + $ShortcutName

$python = Resolve-Python
$buildDir = Join-Path $PSScriptRoot "build"
$releaseRoot = Join-Path $buildDir "releases\$VersionStamp"
$venvDir = Join-Path $buildDir ".venv"
$distDir = Join-Path $releaseRoot $AppName
$mainScript = Join-Path $PSScriptRoot "src\tester_toolbox\app.py"

if (-not (Test-Path $mainScript)) {
    throw "Cannot find $mainScript"
}

if (Test-Path $releaseRoot) {
    Remove-Item $releaseRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $buildDir "temp\pyinstaller-work") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $buildDir "temp\specs") | Out-Null

if (-not (Test-Path $venvDir)) {
    Write-Host "Creating Python virtual environment..."
    & $python -m venv $venvDir
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create Python virtual environment."
    }
}

$venvPython = Join-Path $venvDir "Scripts\python.exe"
Write-Host "Installing Python packaging dependencies..."
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upgrade pip."
}
& $venvPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install Python dependencies."
}

Write-Host "Packaging portable desktop app with PyInstaller..."
& $venvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name $AppName `
    --distpath $releaseRoot `
    --workpath (Join-Path $buildDir "temp\pyinstaller-work") `
    --specpath (Join-Path $buildDir "temp\specs") `
    $mainScript

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

$setupSource = Join-Path $PSScriptRoot "third_party\Setup"
$setupTarget = Join-Path $distDir "third_party\Setup"
if (-not (Test-Path $setupSource)) {
    Write-Warning "third_party\Setup not found. Packaged app may be unable to run performance regression location."
} else {
    Write-Host "Copying third_party\Setup into release package..."
    New-Item -ItemType Directory -Force -Path (Split-Path $setupTarget -Parent) | Out-Null
    if (Test-Path $setupTarget) {
        Remove-Item $setupTarget -Recurse -Force
    }
    Copy-Item -Recurse -Force $setupSource $setupTarget
}

$exePath = Join-Path $distDir "$AppName.exe"
$shortcutPath = Join-Path $buildDir "$ShortcutName.lnk"
Get-ChildItem $buildDir -Filter "*.lnk" -File -ErrorAction SilentlyContinue | Remove-Item -Force

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = Split-Path $exePath -Parent
$shortcut.IconLocation = "$exePath,0"
$shortcut.Description = $shortcutDescription
$shortcut.Save()

Write-Host ""
Write-Host "Done."
Write-Host "Release version: $VersionStamp"
Write-Host "Portable executable: $exePath"
Write-Host "Shortcut: $shortcutPath"
