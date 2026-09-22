param(
    [ValidateSet("update", "status")]
    [string] $Mode = "update"
)

# Compatibility forwarder only.
# Canonical root update-repo.* launchers are managed by tool.git-project.
$ErrorActionPreference = "Stop"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git was not found in PATH."
}
$RootOutput = & git rev-parse --show-toplevel 2>$null
if ($LASTEXITCODE -ne 0 -or -not $RootOutput) {
    throw "Run update-repo.ps1 from inside a Git repository."
}
$Root = ($RootOutput | Select-Object -First 1).Trim()

$GitTool = Join-Path $Root "tools/tool.git-project/git-project.ps1"
if (-not (Test-Path -LiteralPath $GitTool -PathType Leaf)) {
    throw "tool.git-project is not initialized. Run .\bootstrap.ps1 first."
}

& $GitTool $Mode -RepoRoot $Root
if ($LASTEXITCODE -ne 0) {
    throw "Generic project dependency $Mode failed."
}
if ($Mode -eq "status") {
    return
}

$Hook = Join-Path $Root "tools/tool.scad-project/consumer/post-update.ps1"
if (-not (Test-Path -LiteralPath $Hook -PathType Leaf)) {
    throw "SCAD post-update hook not found at $Hook"
}
& $Hook -RepoRoot $Root
