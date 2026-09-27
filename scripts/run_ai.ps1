# Local server only. .env is data, never evaluated as PowerShell code.
param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot
$envPath = Join-Path $projectRoot '.env'
if (Test-Path -LiteralPath $envPath) {
    foreach ($line in [System.IO.File]::ReadAllLines($envPath)) {
        if ($line -match '^\s*(#|$)') { continue }
        if ($line -notmatch '^([A-Z][A-Z0-9_]*)=(.*)$') { throw 'Invalid .env assignment; values were not printed.' }
        $name, $value = $Matches[1], $Matches[2].Trim()
        if ($name -notmatch '^(OPENAI_|GRADIUM_|REELS_|CALENDAR_|GOOGLE_|MICROSOFT_|PROACTIVE_|DATE_SCORING_|CHANDELLE_DEV$)') { continue }
        if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }
}
# Use python from this project's environment. No installation or deployment.
& (Join-Path $projectRoot '.venv\Scripts\python.exe') -m uvicorn backend.api.app:app --host 127.0.0.1 --port $Port
