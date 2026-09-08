param(
    [switch] $SkipUpdate
)

$ErrorActionPreference = "Stop"

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)]
        [string[]] $Args,
        [switch] $AllowFailure
    )

    & git @Args
    $Code = $LASTEXITCODE
    if (-not $AllowFailure -and $Code -ne 0) {
        throw "git $($Args -join ' ') failed with exit code $Code."
    }
    return $Code
}

function Get-RepoRoot {
    $Root = (& git rev-parse --show-toplevel 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $Root) {
        throw "Run bootstrap.ps1 from inside a Git repository."
    }
    return $Root.Trim()
}

function Get-ConfiguredSubmodules {
    param([string] $RepoRoot)

    $GitModules = Join-Path $RepoRoot ".gitmodules"
    if (-not (Test-Path $GitModules)) { return @() }

    $Rows = @()
    $PathLines = & git config -f $GitModules --get-regexp '^submodule\..*\.path$' 2>$null
    if ($LASTEXITCODE -ne 0) { return @() }

    foreach ($Line in $PathLines) {
        if (-not $Line) { continue }
        $Parts = $Line -split '\s+', 2
        if ($Parts.Count -ne 2) { continue }

        $Key = $Parts[0]
        $Path = $Parts[1].Trim()
        $Name = $Key -replace '^submodule\.', '' -replace '\.path$', ''
        $Url = (& git config -f $GitModules --get "submodule.$Name.url" 2>$null)
        if (-not $Url) { throw ".gitmodules entry '$Name' has a path but no URL." }

        $Rows += [PSCustomObject]@{ Name=$Name; Path=$Path; Url=$Url.Trim() }
    }
    return $Rows
}

function Test-Gitlink {
    param([string] $RepoRoot, [string] $Path)
    $Entry = & git -C $RepoRoot ls-files --stage -- $Path 2>$null
    return ($LASTEXITCODE -eq 0 -and $Entry -match '^160000\s')
}

function Ensure-SubmoduleRegistration {
    param([string] $RepoRoot, $Submodule)

    $Path = $Submodule.Path
    $Url = $Submodule.Url
    $FullPath = Join-Path $RepoRoot $Path

    if (Test-Gitlink -RepoRoot $RepoRoot -Path $Path) {
        Write-Host "Registered: $Path"
        return
    }

    Write-Host "Registering missing gitlink: $Path"

    $Parent = Split-Path $FullPath -Parent
    if ($Parent -and -not (Test-Path $Parent)) {
        New-Item -ItemType Directory -Force -Path $Parent | Out-Null
    }

    if (Test-Path $FullPath) {
        $Children = @(Get-ChildItem -Force $FullPath -ErrorAction SilentlyContinue)
        if ($Children.Count -eq 0) {
            Remove-Item -Force $FullPath
        }
        elseif (-not (Test-Path (Join-Path $FullPath ".git"))) {
            throw "Cannot register '$Path': target contains non-submodule files."
        }
    }

    Invoke-Git -Args @(
        "-C", $RepoRoot, "submodule", "add", "--force", $Url, $Path
    ) | Out-Null

    if (-not (Test-Gitlink -RepoRoot $RepoRoot -Path $Path)) {
        throw "Submodule registration did not create gitlink mode 160000 for '$Path'."
    }
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git was not found. Install Git before running bootstrap."
}

$RepoRoot = Get-RepoRoot
Set-Location $RepoRoot

Write-Host ""
Write-Host "SCAD project bootstrap"
Write-Host "Repository: $RepoRoot"
Write-Host ""

$Submodules = @(Get-ConfiguredSubmodules -RepoRoot $RepoRoot)
if ($Submodules.Count -eq 0) {
    throw "No submodules are declared in .gitmodules."
}

foreach ($Submodule in $Submodules) {
    Ensure-SubmoduleRegistration -RepoRoot $RepoRoot -Submodule $Submodule
}

Write-Host ""
Write-Host "Synchronizing submodule URLs..."
Invoke-Git -Args @("-C", $RepoRoot, "submodule", "sync") | Out-Null

if (-not $SkipUpdate) {
    Write-Host "Initializing/restoring pinned submodule commits..."
    $Paths = @($Submodules | ForEach-Object { $_.Path })
    $UpdateArgs = @("-C", $RepoRoot, "submodule", "update", "--init", "--") + $Paths
    Invoke-Git -Args $UpdateArgs | Out-Null
}

foreach ($Submodule in $Submodules) {
    if (-not (Test-Gitlink -RepoRoot $RepoRoot -Path $Submodule.Path)) {
        throw "Bootstrap validation failed: '$($Submodule.Path)' is not a gitlink (160000)."
    }
}

Write-Host ""
Write-Host "Bootstrap complete. All declared submodules have gitlinks."
Write-Host ""
& git -C $RepoRoot submodule status
if ($LASTEXITCODE -ne 0) { throw "Unable to read final submodule status." }

Write-Host ""
Write-Host "Review parent repository changes with: git status"
