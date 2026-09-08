param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $Arguments
)

$ErrorActionPreference = "Stop"

$ToolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SourceRoot = Join-Path $ToolRoot "src"

$env:PYTHONPATH = if ($env:PYTHONPATH) {
    "$SourceRoot;$env:PYTHONPATH"
} else {
    $SourceRoot
}

$Python = Get-Command python -ErrorAction SilentlyContinue
if ($Python) {
    & $Python.Source -m scad_project.cli @Arguments
    exit $LASTEXITCODE
}

$Py = Get-Command py -ErrorAction SilentlyContinue
if ($Py) {
    & $Py.Source -3 -m scad_project.cli @Arguments
    exit $LASTEXITCODE
}

throw "Python 3 was not found. Install Python 3 or run the project tooling through the SCAD toolchain container."
