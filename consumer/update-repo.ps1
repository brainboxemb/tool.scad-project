$ErrorActionPreference = "Stop"

$Root = (& git rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0 -or -not $Root) {
    throw "Run update-repo.ps1 from inside a Git repository."
}

$Tool = Join-Path $Root "tools/tool.scad-project/scad-project.ps1"
if (-not (Test-Path $Tool -PathType Leaf)) {
    throw "tool.scad-project is not initialized. Run .\bootstrap.ps1 first."
}

& $Tool --project $Root repo-update
exit $LASTEXITCODE
