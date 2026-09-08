$ErrorActionPreference = "Stop"

$Tool = Join-Path $PSScriptRoot "tools/tool.scad-project/scad-project.ps1"
if (-not (Test-Path $Tool)) {
    throw "tool.scad-project is not initialized. Run .\bootstrap.ps1 first."
}

& $Tool repo-update
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
