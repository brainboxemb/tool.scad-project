$ErrorActionPreference = "Stop"

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)]
        [string[]] $Args,
        [string] $WorkingDirectory = ""
    )
    if ($WorkingDirectory) {
        & git -C $WorkingDirectory @Args
    } else {
        & git @Args
    }
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Args -join ' ') failed with exit code $LASTEXITCODE."
    }
}

function Get-RepoRoot {
    $Root = (& git rev-parse --show-toplevel 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $Root) {
        throw "Run update-repo.ps1 from inside a Git repository."
    }
    return $Root.Trim()
}

function Get-DependencyPolicy {
    param([string] $ProjectFile)

    if (-not (Test-Path $ProjectFile)) {
        throw "project.yml not found: $ProjectFile"
    }

    # Parse only the small dependency subset needed before Python is available.
    $Lines = Get-Content $ProjectFile
    $Dependencies = @()

    $Section = ""
    $Current = $null
    $InTool = $false

    foreach ($Raw in $Lines) {
        $Line = $Raw.TrimEnd()
        if (-not $Line.Trim() -or $Line.TrimStart().StartsWith("#")) {
            continue
        }

        $Indent = $Line.Length - $Line.TrimStart().Length
        $Text = $Line.Trim()

        if ($Indent -eq 0) {
            if ($Current) {
                $Dependencies += [PSCustomObject]$Current
                $Current = $null
            }

            $InTool = $false
            if ($Text -eq "tooling:") {
                $Section = "tooling"
            } elseif ($Text -eq "externals:") {
                $Section = "externals"
            } else {
                $Section = ""
            }
            continue
        }

        if ($Section -eq "tooling") {
            if ($Indent -eq 2 -and $Text -eq "tool_scad_project:") {
                if ($Current) {
                    $Dependencies += [PSCustomObject]$Current
                }
                $Current = [ordered]@{
                    Name = "tool.scad-project"
                    Role = "tooling"
                    Type = "git-submodule"
                    Url = "https://github.com/brainboxemb/tool.scad-project.git"
                    Path = "tools/tool.scad-project"
                    Ref = ""
                }
                $InTool = $true
                continue
            }

            if ($InTool -and $Indent -ge 4 -and $Text -match '^([^:]+):\s*(.*)$') {
                $Key = $Matches[1].Trim()
                $Value = $Matches[2].Trim().Trim('"').Trim("'")
                switch ($Key) {
                    "type" { $Current.Type = $Value }
                    "url"  { $Current.Url = $Value }
                    "path" { $Current.Path = $Value }
                    "ref"  { $Current.Ref = $Value }
                }
            }
            continue
        }

        if ($Section -eq "externals") {
            if ($Indent -eq 2 -and $Text -match '^-\s*name:\s*(.+)$') {
                if ($Current) {
                    $Dependencies += [PSCustomObject]$Current
                }
                $Current = [ordered]@{
                    Name = $Matches[1].Trim().Trim('"').Trim("'")
                    Role = "external"
                    Type = "git-submodule"
                    Url = ""
                    Path = ""
                    Ref = ""
                }
                continue
            }

            if ($Current -and $Indent -ge 4 -and $Text -match '^([^:]+):\s*(.*)$') {
                $Key = $Matches[1].Trim()
                $Value = $Matches[2].Trim().Trim('"').Trim("'")
                switch ($Key) {
                    "type" { $Current.Type = $Value }
                    "url"  { $Current.Url = $Value }
                    "path" { $Current.Path = $Value }
                    "ref"  { $Current.Ref = $Value }
                }
            }
        }
    }

    if ($Current) {
        $Dependencies += [PSCustomObject]$Current
    }

    foreach ($Dependency in $Dependencies) {
        if ($Dependency.Type -ne "git-submodule") {
            throw "Unsupported dependency type '$($Dependency.Type)' for $($Dependency.Name)."
        }
        if (-not $Dependency.Url)  { throw "Missing url for dependency $($Dependency.Name)." }
        if (-not $Dependency.Path) { throw "Missing path for dependency $($Dependency.Name)." }
        if (-not $Dependency.Ref)  { throw "Missing ref for dependency $($Dependency.Name)." }
    }

    return @($Dependencies)
}

function Test-Gitlink {
    param([string] $RepoRoot, [string] $Path)
    $Entry = & git -C $RepoRoot ls-files --stage -- $Path 2>$null
    return ($LASTEXITCODE -eq 0 -and $Entry -match '^160000\s')
}

function Ensure-DependencyRegistration {
    param([string] $RepoRoot, $Dependency)

    $Path = $Dependency.Path
    $FullPath = Join-Path $RepoRoot $Path

    if (Test-Gitlink -RepoRoot $RepoRoot -Path $Path) {
        return
    }

    $Parent = Split-Path $FullPath -Parent
    if ($Parent -and -not (Test-Path $Parent)) {
        New-Item -ItemType Directory -Force -Path $Parent | Out-Null
    }

    if (Test-Path $FullPath) {
        $Children = @(Get-ChildItem -Force $FullPath -ErrorAction SilentlyContinue)
        if ($Children.Count -eq 0) {
            Remove-Item -Force $FullPath
        } else {
            & git -C $FullPath rev-parse --git-dir 2>$null | Out-Null
            if ($LASTEXITCODE -ne 0) {
                throw "Cannot register $($Dependency.Name): target contains non-Git files: $Path"
            }
        }
    }

    Write-Host "Registering $($Dependency.Name): $Path"
    Invoke-Git -Args @(
        "submodule", "add", "--force", $Dependency.Url, $Path
    ) -WorkingDirectory $RepoRoot

    if (-not (Test-Gitlink -RepoRoot $RepoRoot -Path $Path)) {
        throw "Registration did not create gitlink mode 160000 for $Path."
    }
}

function Assert-CleanDependency {
    param([string] $RepoRoot, $Dependency)
    $FullPath = Join-Path $RepoRoot $Dependency.Path
    $Status = (& git -C $FullPath status --porcelain)
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect dependency $($Dependency.Name)."
    }
    if ($Status) {
        throw "Dependency '$($Dependency.Name)' has local changes: $($Dependency.Path)"
    }
}

function Get-LatestStableTag {
    param([string] $Path)

    $Tags = & git -C $Path tag --list
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to list tags for $Path."
    }

    $Parsed = @()
    foreach ($Tag in $Tags) {
        if ($Tag -match '^v?(\d+)\.(\d+)\.(\d+)$') {
            $Parsed += [PSCustomObject]@{
                Tag = $Tag
                Major = [int]$Matches[1]
                Minor = [int]$Matches[2]
                Patch = [int]$Matches[3]
            }
        }
    }

    if ($Parsed.Count -eq 0) {
        throw "No stable semantic-version tags found for $Path."
    }

    return (
        $Parsed |
        Sort-Object @{Expression="Major";Descending=$true},
                    @{Expression="Minor";Descending=$true},
                    @{Expression="Patch";Descending=$true} |
        Select-Object -First 1
    ).Tag
}

function Resolve-DependencyRef {
    param([string] $Path, [string] $Ref)

    Invoke-Git -Args @("fetch", "--prune", "--tags", "origin") -WorkingDirectory $Path

    if ($Ref -eq "latest") {
        $Tag = Get-LatestStableTag -Path $Path
        return [PSCustomObject]@{ Checkout = $Tag; WorkflowRef = $Tag }
    }

    & git -C $Path rev-parse --verify "refs/tags/$Ref^{commit}" 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        return [PSCustomObject]@{ Checkout = $Ref; WorkflowRef = $Ref }
    }

    & git -C $Path rev-parse --verify "refs/remotes/origin/$Ref^{commit}" 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        return [PSCustomObject]@{ Checkout = "origin/$Ref"; WorkflowRef = $Ref }
    }

    throw "Ref '$Ref' for $Path is neither a tag nor a branch on origin."
}

function Update-WorkflowRefs {
    param([string] $RepoRoot, [string] $WorkflowRef)

    $WorkflowDir = Join-Path $RepoRoot ".github/workflows"
    if (-not (Test-Path $WorkflowDir)) {
        return
    }

    $Pattern = '(brainboxemb/tool\.scad-project/\.github/workflows/(?:project-build|project-verify)\.yml)@[^\s''"]+'

    Get-ChildItem $WorkflowDir -File |
        Where-Object { $_.Extension -in @(".yml", ".yaml") } |
        ForEach-Object {
            $Old = Get-Content $_.FullName -Raw
            $New = [regex]::Replace($Old, $Pattern, ('$1@' + $WorkflowRef))
            if ($New -ne $Old) {
                Set-Content -Path $_.FullName -Value $New -NoNewline
                Write-Host "Updated workflow ref: $($_.FullName)"
            }
        }
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git was not found."
}

$RepoRoot = Get-RepoRoot
Set-Location $RepoRoot

$Dependencies = @(Get-DependencyPolicy -ProjectFile (Join-Path $RepoRoot "project.yml"))
if ($Dependencies.Count -eq 0) {
    throw "No versioned dependencies found in project.yml."
}

foreach ($Dependency in $Dependencies) {
    Ensure-DependencyRegistration -RepoRoot $RepoRoot -Dependency $Dependency
}

Invoke-Git -Args @("submodule", "sync") -WorkingDirectory $RepoRoot
$DirectPaths = @($Dependencies | ForEach-Object { $_.Path })
$UpdateArgs = @("submodule", "update", "--init", "--") + $DirectPaths
Invoke-Git -Args $UpdateArgs -WorkingDirectory $RepoRoot

$Ordered = @(
    @($Dependencies | Where-Object { $_.Role -ne "tooling" }) +
    @($Dependencies | Where-Object { $_.Role -eq "tooling" })
)

$Results = @()
$ToolWorkflowRef = $null

foreach ($Dependency in $Ordered) {
    Assert-CleanDependency -RepoRoot $RepoRoot -Dependency $Dependency

    $FullPath = Join-Path $RepoRoot $Dependency.Path
    $Old = (& git -C $FullPath rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to read current commit for $($Dependency.Name)."
    }

    $Resolved = Resolve-DependencyRef -Path $FullPath -Ref $Dependency.Ref
    Invoke-Git -Args @("checkout", "--detach", $Resolved.Checkout) -WorkingDirectory $FullPath

    $New = (& git -C $FullPath rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to read updated commit for $($Dependency.Name)."
    }

    $Results += [PSCustomObject]@{
        Name = $Dependency.Name
        Path = $Dependency.Path
        Requested = $Dependency.Ref
        Resolved = $Resolved.WorkflowRef
        Old = $Old
        New = $New
    }

    if ($Dependency.Role -eq "tooling") {
        $ToolWorkflowRef = $Resolved.WorkflowRef
    }
}

if ($ToolWorkflowRef) {
    Update-WorkflowRefs -RepoRoot $RepoRoot -WorkflowRef $ToolWorkflowRef
}

Write-Host ""
Write-Host "Repository dependency update"
Write-Host "============================"

foreach ($Result in $Results) {
    $State = if ($Result.Old -eq $Result.New) { "unchanged" } else { "updated" }
    Write-Host ""
    Write-Host "$($Result.Name): $($Result.Requested) -> $($Result.Resolved) [$State]"
    Write-Host "  old  : $($Result.Old)"
    Write-Host "  new  : $($Result.New)"
    Write-Host "  path : $($Result.Path)"
}

Write-Host ""
Write-Host "Changes are intentionally left uncommitted."
Write-Host ""
git status --short
