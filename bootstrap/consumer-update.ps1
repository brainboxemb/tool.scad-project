param(
    [ValidateSet("update", "status")]
    [string] $Mode = "update"
)

$ErrorActionPreference = "Stop"

function Unquote-ProjectValue {
    param([string] $Value)

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
    param([string] $ProjectFile)

    $InDependencies = $false
    $InScadTool = $false

    foreach ($Line in Get-Content -LiteralPath $ProjectFile) {
        if ($Line -match '^[^\s]') {
            $InDependencies = ($Line -match '^dependencies:\s*$')
            if (-not $InDependencies) { $InScadTool = $false }
            continue
        }

        if (-not $InDependencies) { continue }

        if ($Line -match '^  - name:\s*(.+?)\s*$') {
            $InScadTool = ((Unquote-ProjectValue $Matches[1]) -eq 'tool.scad-project')
            continue
        }

        if ($InScadTool -and $Line -match '^    ref:\s*(.+?)\s*$') {
            return Unquote-ProjectValue $Matches[1]
        }
    }

    throw "project.yml does not declare a ref for dependency 'tool.scad-project'."
}

function Sync-ScadWorkflowRefs {
    param(
        [string] $Root,
        [string] $ToolRef
    )

    $WorkflowRoot = Join-Path $Root ".github/workflows"
    if (-not (Test-Path -LiteralPath $WorkflowRoot -PathType Container)) {
        return
    }

    $Pattern = '(brainboxemb/tool\.scad-project/\.github/workflows/(?:project-build|project-verify|project-production|project-release)\.yml)@[^\s"'']+'
    $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

    foreach ($Workflow in Get-ChildItem -LiteralPath $WorkflowRoot -File | Where-Object { $_.Extension -in @('.yml', '.yaml') }) {
        $Text = [System.IO.File]::ReadAllText($Workflow.FullName)
        $Updated = [regex]::Replace(
            $Text,
            $Pattern,
            [System.Text.RegularExpressions.MatchEvaluator]{
                param($Match)
                return "$($Match.Groups[1].Value)@$ToolRef"
            }
        )

        if ($Updated -ne $Text) {
            [System.IO.File]::WriteAllText($Workflow.FullName, $Updated, $Utf8NoBom)
            Write-Host "Updated SCAD workflow ref: $($Workflow.FullName.Substring($Root.Length + 1)) -> $ToolRef"
        }
    }
}

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
    Write-Host "SCAD repository status complete."
    return
}

$ToolRef = Get-ConfiguredScadToolRef (Join-Path $Root "project.yml")
Sync-ScadWorkflowRefs -Root $Root -ToolRef $ToolRef
Write-Host "SCAD repository update complete."
