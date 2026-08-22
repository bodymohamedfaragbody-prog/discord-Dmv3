# Run the Discord DM Dashboard from PowerShell.
# Usage: Right-click and Run with PowerShell, or from PowerShell prompt:
#   .\run.ps1
# If 'python' is not on your PATH, set $pythonExe to the absolute path of Python executable.

$pythonExe = 'python'
$script = Join-Path $PSScriptRoot 'main.py'

try {
    Write-Host "Running: $pythonExe $script"
    & $pythonExe $script
} catch {
    Write-Error "Failed to start python. Edit run.ps1 and set `'$pythonExe'` to the full path of your python.exe. Error: $_"
}
