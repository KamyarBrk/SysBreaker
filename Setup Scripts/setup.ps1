<#
.SYNOPSIS
  Create a Python virtual environment and install dependencies from requirements.txt.

.DESCRIPTION
  - Default venv dir: .venv
  - Default minimum Python version: 3.10 (configurable)
  - Default maximum Python version: 3.12 (configurable) — script will refuse Python newer than 3.12.
  - Attempts "python" then "python3" if needed.
  - To keep the virtualenv activated in your current PowerShell session, dot-source this script:
      . .\setup.ps1
  - If scripts are blocked: run (non-persistently)
      powershell -ExecutionPolicy Bypass -File .\setup.ps1
#>

param(
    [string]$VenvDir = ".venv",
    [string]$PythonExe = "python",
    [string]$RequirementsFile = "$PSScriptRoot\requirements.txt",
    [Version]$MinPythonVersion = "3.10.0",
    [Version]$MaxPythonVersion = "3.12.8"
)

function Write-ErrorAndExit($msg, [int]$code = 1) {
    Write-Host ""
    Write-Host "ERROR: $msg" -ForegroundColor Red
    exit $code
}

Write-Host "== Setup script starting =="

# Resolve python executable (try python then python3)
$pythonCandidates = @($PythonExe, "python3") | Select-Object -Unique
$foundPython = $null
$foundVersion = $null

foreach ($cand in $pythonCandidates) {
    try {
        $verOut = & $cand -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>&1
        if ($LASTEXITCODE -eq 0 -or ($verOut -and $verOut -match '^\d+\.\d+(\.\d+)?$')) {
            try {
                $foundVersion = [Version]$verOut.Trim()
                $foundPython = $cand
                break
            } catch {
                # parse failed - continue
            }
        }
    } catch {
        # ignore and try next
    }
}

if (-not $foundPython) {
    Write-ErrorAndExit "No usable Python executable found. Make sure 'python' or 'python3' is on PATH."
}

Write-Host "Found Python executable: $foundPython (version $foundVersion)"

# Enforce minimum and maximum Python versions
if ($foundVersion -lt $MinPythonVersion) {
    Write-ErrorAndExit "Python version $foundVersion found but minimum required is $MinPythonVersion. Please install a newer Python."
}

if ($foundVersion -gt $MaxPythonVersion) {
    Write-ErrorAndExit "Python version $foundVersion is newer than the maximum supported version $MaxPythonVersion. Please use Python $MaxPythonVersion or earlier."
}

# Check requirements.txt exists
if (-not (Test-Path $RequirementsFile)) {
    Write-ErrorAndExit "Requirements file '$RequirementsFile' not found in $(Get-Location)."
}

# Create venv (if not present)
$venvPath = (Resolve-Path -LiteralPath $VenvDir -ErrorAction SilentlyContinue)
if ($venvPath) {
    Write-Host "Virtual environment directory '$VenvDir' already exists. Skipping creation."
} else {
    Write-Host "Creating virtual environment in '$VenvDir'..."
    $createResult = & $foundPython -m venv $VenvDir 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host $createResult
        Write-ErrorAndExit "Failed to create virtual environment."
    }
    Write-Host "Virtual environment created."
}

# Determine python executable inside venv (Windows style)
$venvPython = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    # Fallback: try tools for non-Windows users (Scripts -> bin)
    $venvPython = Join-Path $VenvDir "bin/python"
}

if (-not (Test-Path $venvPython)) {
    Write-ErrorAndExit "Unable to locate python inside the virtual environment at '$VenvDir'."
}

# Upgrade pip and install requirements
Write-Host "Upgrading pip inside venv..."
& $venvPython -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) {
    Write-ErrorAndExit "Failed to upgrade pip inside virtual environment."
}

Write-Host "Installing requirements from '$RequirementsFile'..."
& $venvPython -m pip install -r $RequirementsFile
if ($LASTEXITCODE -ne 0) {
    Write-ErrorAndExit "pip install failed. See output above for errors."
}

Write-Host "Installing Ollama models..."
ollama pull nomic-embed-text

Write-Host ""
Write-Host "== Success! Dependencies installed. ==" -ForegroundColor Green
Write-Host ""

# Activation instructions
$activatePath = Join-Path $VenvDir "Scripts\Activate.ps1"
$activatePathUnix = Join-Path $VenvDir "bin/activate"

Write-Host "To activate the virtual environment in PowerShell (current session), run:"
Write-Host "  . $PWD\$activatePath" -ForegroundColor Cyan
Write-Host ""
Write-Host "If you prefer cmd.exe:"
Write-Host "  $PWD\$VenvDir\Scripts\activate.bat" -ForegroundColor Cyan
Write-Host ""
Write-Host "In Git Bash or WSL:"
Write-Host "  source $PWD/$activatePathUnix" -ForegroundColor Cyan
Write-Host ""

Write-Host ""
Write-Host "Notes:"
Write-Host "- This repository requires Python versions between $MinPythonVersion and $MaxPythonVersion (inclusive)." -ForegroundColor Yellow
Write-Host "- If you see 'running scripts is disabled on this system', run (one-time for current user):" -ForegroundColor Yellow
Write-Host "    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser"
Write-Host "  Or run the setup non-persistently with:"
Write-Host "    powershell -ExecutionPolicy Bypass -File .\\setup.ps1"
Write-Host ""
Write-Host "Done. Windows users should now run .venv\Scripts\activate.ps1 in the terminal to activate the virtual environment." -ForegroundColor Yellow
Write-Host "You should then see '(.venv)' in green." -ForegroundColor Yellow
Write-Host ""
