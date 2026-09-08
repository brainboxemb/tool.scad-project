param(
    [switch] $SkipProjectExternals
)

$ErrorActionPreference = "Stop"

$ToolRepository = "https://github.com/brainboxemb/tool.scad-project.git"
$ToolPath = "tools/tool.scad-project"

if (-not (Test-Path ".git")) {
    throw "Run bootstrap.ps1 from the root of a Git repository."
}

Write-Host "SCAD project bootstrap"
Write-Host "Tool path: $ToolPath"

$Registered = $false
if (Test-Path ".gitmodules") {
    $ConfiguredPaths = git config -f .gitmodules --get-regexp 'submodule\..*\.path' 2>$null
    if ($LASTEXITCODE -eq 0) {
        foreach ($Line in $ConfiguredPaths) {
            if (($Line -split '\s+', 2)[1] -eq $ToolPath) {
                $Registered = $true
                break
            }
        }
    }
}

if (-not $Registered) {
    if (Test-Path $ToolPath) {
        $Existing = Get-ChildItem -Force $ToolPath -ErrorAction SilentlyContinue
        if ($Existing) {
            throw "Cannot add tool submodule because '$ToolPath' already contains files."
        }
        Remove-Item -Force $ToolPath -ErrorAction SilentlyContinue
    }

    Write-Host "Registering tool.scad-project as a Git submodule..."
    git submodule add $ToolRepository $ToolPath
    if ($LASTEXITCODE -ne 0) {
        throw "git submodule add failed."
    }
}

Write-Host "Initializing local project tooling..."
git submodule update --init --recursive -- $ToolPath
if ($LASTEXITCODE -ne 0) {
    throw "Could not initialize $ToolPath."
}

$Launcher = Join-Path $ToolPath "scad-project.ps1"
if (-not (Test-Path $Launcher)) {
    throw "Tool launcher not found: $Launcher"
}

if (-not $SkipProjectExternals) {
    Write-Host "Initializing configured project externals..."
    & $Launcher externals-init
    if ($LASTEXITCODE -ne 0) {
        throw "Project external initialization failed."
    }
}

Write-Host ""
Write-Host "Bootstrap complete."
Write-Host "Local tool:"
Write-Host "  .\$ToolPath\scad-project.ps1 <command>"
