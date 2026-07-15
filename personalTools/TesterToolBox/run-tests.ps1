$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$env:PYTHONPATH = (Join-Path $Root "src") + [IO.Path]::PathSeparator + $Root
py (Join-Path $Root "tests\run_tests.py")
exit $LASTEXITCODE