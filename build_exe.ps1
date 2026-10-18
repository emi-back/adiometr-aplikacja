# Buduje samodzielny plik dist\Audiogram.exe za pomocą PyInstallera.
# Uruchomienie: .\build_exe.ps1  (z katalogu desktop_app)

$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$python = Join-Path $root "venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Nie znaleziono $python - upewnij sie, ze venv istnieje (patrz README/plans)."
}

foreach ($path in @("build", "dist", "Audiogram.spec")) {
    $full = Join-Path $root $path
    if (Test-Path $full) {
        Remove-Item -Recurse -Force $full
    }
}

& $python -m PyInstaller `
    --name Audiogram `
    --onefile `
    --windowed `
    --hidden-import=serial.tools.list_ports_windows `
    (Join-Path $root "main.py")

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller zakonczyl sie bledem (kod $LASTEXITCODE)."
}

Write-Output ""
Write-Output "Gotowe: $(Join-Path $root 'dist\Audiogram.exe')"
