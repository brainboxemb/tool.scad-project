$ErrorActionPreference = "Stop"

$Root = (& git rev-parse --show-toplevel 2>$null)
if ($LASTEXITCODE -ne 0 -or -not $Root) { throw "Run update-repo.ps1 from inside a Git repository." }
$Root = $Root.Trim()

$GitTool = Join-Path $Root "tools/tool.git-project/git-project.ps1"
if (-not (Test-Path $GitTool -PathType Leaf)) {
    throw "tool.git-project is not initialized. Run .\bootstrap.ps1 first."
}

& $GitTool update -RepoRoot $Root
if ($LASTEXITCODE -ne 0) { throw "Generic project dependency update failed." }

function Unquote-ProjectValue {
    param([string]$Value)
    $Result = $Value.Trim()
    if ($Result.Length -ge 2) {
        if (($Result.StartsWith('"') -and $Result.EndsWith('"')) -or
            ($Result.StartsWith("'") -and $Result.EndsWith("'"))) {
            return $Result.Substring(1, $Result.Length - 2)
        }
    }
    return $Result
}

function Get-ConfiguredScadToolRef {
    param([string]$ProjectFile)

    $InDependencies = $false
    $TargetDependency = $false
    foreach ($Raw in Get-Content -LiteralPath $ProjectFile) {
        if ($Raw -match '^dependencies:\s*$') {
            $InDependencies = $true
            $TargetDependency = $false
            continue
        }
        if ($InDependencies -and $Raw -match '^\S') { break }
        if (-not $InDependencies) { continue }

        if ($Raw -match '^  - name:\s*(.+)$') {
            $Name = Unquote-ProjectValue $Matches[1]
            $TargetDependency = ($Name -eq "tool.scad-project")
            continue
        }
        if ($TargetDependency -and $Raw -match '^    ref:\s*(.+)$') {
            return Unquote-ProjectValue $Matches[1]
        }
    }
    throw "project.yml does not declare a tool.scad-project dependency ref."
}

$ToolRef = Get-ConfiguredScadToolRef (Join-Path $Root "project.yml")
$WorkflowDir = Join-Path $Root ".github/workflows"
$Pattern = '(brainboxemb/tool\.scad-project/\.github/workflows/(?:project-build|project-verify|project-production|project-release)\.yml)@([^\s"''>]+)'

if (Test-Path $WorkflowDir -PathType Container) {
    Get-ChildItem -LiteralPath $WorkflowDir -File |
        Where-Object { $_.Extension -in @(".yml", ".yaml") } |
        ForEach-Object {
            $Path = $_.FullName
            $Text = [System.IO.File]::ReadAllText($Path)
            $Updated = [regex]::Replace(
                $Text,
                $Pattern,
                [System.Text.RegularExpressions.MatchEvaluator]{
                    param($Match)
                    return $Match.Groups[1].Value + "@" + $ToolRef
                }
            )
            if ($Updated -ne $Text) {
                [System.IO.File]::WriteAllText($Path, $Updated)
                Write-Host "Updated SCAD workflow ref: $($_.Name) -> $ToolRef"
            }
        }
}

Write-Host "Repository dependency update complete."
