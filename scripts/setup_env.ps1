# Script de configuration de l'environnement Python pour LevelUp
# IMPORTANT: utilise Python Windows (python.org), pas MSYS2/Git Bash, pour avoir
# les wheels précompilées de DuckDB (sinon compilation depuis les sources = échec).
#
# Usage: .\scripts\setup_env.ps1

$ErrorActionPreference = "Stop"

# Essayer py (Windows Python Launcher) en priorité
$py = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    # py -3.12 ou py -3.11
    $versions = @("3.12", "3.11", "3.10")
    foreach ($v in $versions) {
        try {
            $out = & py -$v -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $out) {
                $py = & py -$v -c "import sys; print(sys.executable)"
                Write-Host "Python trouve: $py"
                break
            }
        } catch {}
    }
}

if (-not $py) {
    # Fallback: python.exe dans PATH
    $py = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
}

if (-not $py) {
    Write-Host "ERREUR: Python 3.10-3.12 non trouve."
    Write-Host "Installez Python depuis https://www.python.org/downloads/"
    Write-Host "Ou utilisez le Windows Store: winget install Python.Python.3.12"
    exit 1
}

$venvDir = ".venv_windows"
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repoRoot

if (Test-Path $venvDir) {
    Write-Host "Suppression de l'ancien venv..."
    Remove-Item -Recurse -Force $venvDir
}

Write-Host "Creation du venv avec $py ..."
& $py -m venv $venvDir

$pip = Join-Path $venvDir "Scripts\pip.exe"
$pythonExe = Join-Path $venvDir "Scripts\python.exe"

Write-Host "Mise a jour de pip..."
& $pip install --upgrade pip -q

Write-Host "Installation des dependances..."
& $pip install -e ".[dev,spnkr]" -q

Write-Host ""
Write-Host "OK. Environnement pret."
Write-Host "Pour activer: .\.venv_windows\Scripts\Activate.ps1"
Write-Host "Ou (Git Bash): source activate_env.sh"
Write-Host "Python: $pythonExe"
