[CmdletBinding()]
param(
    [int]$Port = 8080,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ModelFile = if ($env:QWEN_MODEL_FILE) { $env:QWEN_MODEL_FILE } else { "Qwen3-30B-A3B-Q4_K_M.gguf" }
$Server = Join-Path $ProjectDir "runtime\llama-server.exe"
$Model = Join-Path $ProjectDir "models\$ModelFile"

if (-not (Test-Path $Server) -or -not (Test-Path $Model)) {
    Write-Host "Runtime or model is missing; running local setup first."
    & (Join-Path $ProjectDir "setup_qwen.ps1")
    if ($LASTEXITCODE -ne 0) { throw "Qwen setup failed" }
}

$Arguments = @((Join-Path $ProjectDir "run_server.py"), "--port", "$Port")
if (-not $NoBrowser) { $Arguments += "--open-browser" }
& python @Arguments
exit $LASTEXITCODE

