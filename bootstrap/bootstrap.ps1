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
    if (-not (Test-Path $GitModules)) {
        return @()
    }

    $Rows = @()
    $PathLines = & git config -f $GitModules --get-regexp '^submodule\..*\.path$' 2>$null
    if ($LASTEXITCODE -ne 0) {
        return @()
    }

    foreach ($Line in $PathLines) {
        if (-not $Line) { continue }

        $Parts = $Line -split '\s+', 2
        if ($Parts.Count -ne 2) { continue }

        $Key = $Parts[0]
        $Path = $Parts[1].Trim()
        $Name = $Key -replace '^submodule\.', '' -replace '\.path$', ''
        $Url = (& git config -f $GitModules --get "submodule.$Name.url" 2>$null)

        if (-not $Url) {
            throw ".gitmodules entry '$Name' has a path but no URL."
        }

        $Rows += [PSCustomObject]@{
            Name = $Name
            Path = $Path
            Url  = $Url.Trim()
        }
    }

    return $Rows
}

function Test-Gitlink {
    param(
        [string] $RepoRoot,
        [string] $Path
    )

    $Entry = & git -C $RepoRoot ls-files --stage -- $Path 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $Entry) {
        return $false
    }

    return ($Entry -match '^160000\s')
}

function Ensure-SubmoduleRegistration {
    param(
        [string] $RepoRoot,
        $Submodule
    )

    $Path = $Submodule.Path
    $Url = $Submodule.Url
    $FullPath = Join-Path $RepoRoot $Path

    if (Test-Gitlink -RepoRoot $RepoRoot -Path $Path) {
        Write-Host "Registered: $Path"
        return
    }

    Write-Host "Repairing/registering gitlink: $Path"

    # A directory can exist from an interrupted bootstrap. If it is already a
    # Git checkout, keep it and let `git submodule add --force` reuse it.
    # If it is empty, remove it because git expects to create the path.
    if (Test-Path $FullPath) {
        $Children = @(Get-ChildItem -Force $FullPath -ErrorAction SilentlyContinue)

        if ($Children.Count -eq 0) {
            Remove-Item -Force $FullPath
        }
        elseif (-not (Test-Path (Join-Path $FullPath ".git"))) {
            throw @"
Cannot register submodule '$Path' because the directory already contains
non-submodule files.

Move or remove that directory and run bootstrap.ps1 again.
"@
        }
    }

    # --force is intentional: it makes recovery possible when the path already
    # contains the expected checkout from an interrupted earlier attempt.
    Invoke-Git -Args @(
        "-C", $RepoRoot,
        "submodule", "add", "--force",
        $Url, $Path
    ) | Out-Null
}

$Git = Get-Command git -ErrorAction SilentlyContinue
if (-not $Git) {
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
    throw @"
No submodules are declared in .gitmodules.

The project template should contain the technical external registrations in
.gitmodules before bootstrap is run.
"@
}

foreach ($Submodule in $Submodules) {
    Ensure-SubmoduleRegistration -RepoRoot $RepoRoot -Submodule $Submodule
}

Write-Host ""
Write-Host "Synchronizing submodule URLs..."
Invoke-Git -Args @("-C", $RepoRoot, "submodule", "sync", "--recursive") | Out-Null

if (-not $SkipUpdate) {
    Write-Host "Initializing/restoring all submodules..."
    Invoke-Git -Args @(
        "-C", $RepoRoot,
        "submodule", "update", "--init", "--recursive"
    ) | Out-Null
}

Write-Host ""
Write-Host "Bootstrap complete."
Write-Host ""
Write-Host "Submodule status:"
& git -C $RepoRoot submodule status --recursive
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read final submodule status."
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "  git status"
Write-Host "  git add .gitmodules"
Write-Host "  git add <new submodule paths>"
Write-Host "  git commit"
