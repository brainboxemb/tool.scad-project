$ErrorActionPreference = "Stop"

$Root = (& git rev-parse --show-toplevel 2>$null)
if ($LASTEXITCODE -ne 0 -or -not $Root) { throw "Run update-repo.ps1 from inside a Git repository." }
$Root = $Root.Trim()

$Tool = Join-Path $Root "tools/tool.scad-project/scad-project.ps1"
if (-not (Test-Path $Tool)) { throw "tool.scad-project is not initialized. Run .\bootstrap.ps1 first." }

& $Tool --project $Root repo-update
if ($LASTEXITCODE -ne 0) { throw "SCAD project dependency update failed." }
