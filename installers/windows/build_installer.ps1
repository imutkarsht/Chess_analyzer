# ==============================================================================
# Chess Analyzer Pro - Windows Inno Setup Builder
# ==============================================================================
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\installers\windows\build_installer.ps1
# ==============================================================================

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path "$ScriptDir\..\.."
$DistDir = "$ProjectRoot\dist\ChessAnalyzerPro"
$IssFile = "$ScriptDir\ChessAnalyzerPro.iss"

# 1. Resolve version from env or src/constants.py
$AppVersion = $env:APP_VERSION
if (-not $AppVersion) {
    $ConstantsFile = "$ProjectRoot\src\constants.py"
    if (Test-Path $ConstantsFile) {
        $content = Get-Content -Path $ConstantsFile -Raw
        if ($content -match 'APP_VERSION\s*=\s*["\x27]([^"\x27]+)["\x27]') {
            $AppVersion = $Matches[1]
        }
    }
}
if (-not $AppVersion) {
    Write-Error "Could not resolve APP_VERSION. Set `$env:APP_VERSION or ensure src/constants.py exists."
}

Write-Host "==> Building Windows Installer for Chess Analyzer Pro v$AppVersion..." -ForegroundColor Cyan

# 2. Check PyInstaller bundle
if (-not (Test-Path $DistDir)) {
    Write-Error "PyInstaller bundle not found at: $DistDir`nPlease run 'pyinstaller build.spec' first."
}

# 3. Locate ISCC.exe (Inno Setup Compiler)
$Iscc = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
if (-not $Iscc) {
    $PossiblePaths = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
    )
    foreach ($P in $PossiblePaths) {
        if (Test-Path $P) {
            $Iscc = $P
            break
        }
    }
}

if (-not $Iscc) {
    Write-Error "Inno Setup Compiler (ISCC.exe) not found. Please install Inno Setup 6: https://jrsoftware.org/isinfo.php"
}

# 4. Compile Installer
Write-Host "==> Running Inno Setup compiler ($Iscc)..." -ForegroundColor Cyan
& $Iscc "/DAppVersion=$AppVersion" $IssFile

Write-Host "==> Windows Setup created successfully in installers\windows\Output\" -ForegroundColor Green

