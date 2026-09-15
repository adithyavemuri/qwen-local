[CmdletBinding()]
param(
    [switch]$Preflight,
    [switch]$RuntimeOnly,
    [switch]$ModelOnly
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (@($Preflight, $RuntimeOnly, $ModelOnly).Where({ $_ }).Count -gt 1) {
    throw "Choose only one of -Preflight, -RuntimeOnly, or -ModelOnly."
}

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SourceDir = Join-Path $ProjectDir "build\llama.cpp"
$ModelDir = Join-Path $ProjectDir "models"
$RuntimeDir = Join-Path $ProjectDir "runtime"
$DownloadDir = Join-Path $ProjectDir "downloads"
$LlamaRef = if ($env:LLAMA_CPP_REF) { $env:LLAMA_CPP_REF } else { "b10621" }
$ModelFile = if ($env:QWEN_MODEL_FILE) { $env:QWEN_MODEL_FILE } else { "Qwen3-30B-A3B-Q4_K_M.gguf" }
$ModelUrl = if ($env:QWEN_MODEL_URL) { $env:QWEN_MODEL_URL } else {
    "https://huggingface.co/Qwen/Qwen3-30B-A3B-GGUF/resolve/main/$ModelFile`?download=true"
}
$BuildRuntime = -not $ModelOnly
$DownloadModel = -not $RuntimeOnly

if ($env:PROCESSOR_ARCHITECTURE -ne "AMD64") {
    throw "This setup script currently supports Windows x64 (AMD64), not $env:PROCESSOR_ARCHITECTURE."
}

function Require-Command([string]$Name, [string]$Guidance) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing required command '$Name'. $Guidance"
    }
}

Require-Command git "Install Git for Windows and open a new terminal."
Require-Command curl.exe "Use a supported Windows 10/11 installation or install curl."
if ($BuildRuntime) {
    Require-Command cmake "Install Visual Studio 2022 C++ CMake tools."
    Require-Command cl.exe "Run this script from Developer PowerShell for VS 2022."
}

Write-Host "Windows Qwen preflight"
Write-Host "  Project: $ProjectDir"
Write-Host "  Architecture: $env:PROCESSOR_ARCHITECTURE"
Write-Host "  llama.cpp revision: $LlamaRef"
Write-Host "  Model: $ModelFile (approximately 18.6 GB)"
Write-Host "  All generated files stay under this project directory."
if ($Preflight) {
    Write-Host "Preflight passed. Nothing was downloaded or compiled."
    exit 0
}

New-Item -ItemType Directory -Force -Path $ModelDir, $RuntimeDir, $DownloadDir | Out-Null

if ($BuildRuntime) {
    if (-not (Test-Path (Join-Path $SourceDir ".git"))) {
        if (Test-Path $SourceDir) {
            $items = @(Get-ChildItem -Force $SourceDir)
            if ($items.Count -gt 0) { throw "Source destination exists but is not a Git checkout: $SourceDir" }
            Remove-Item $SourceDir
        }
        git clone https://github.com/ggml-org/llama.cpp.git $SourceDir
        if ($LASTEXITCODE -ne 0) { throw "git clone failed" }
    }
    git -C $SourceDir fetch --tags origin $LlamaRef
    if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }
    git -C $SourceDir checkout --detach FETCH_HEAD
    if ($LASTEXITCODE -ne 0) { throw "git checkout failed" }

    $BuildDir = Join-Path $SourceDir "build-windows"
    cmake -S $SourceDir -B $BuildDir -A x64 -DBUILD_SHARED_LIBS=OFF
    if ($LASTEXITCODE -ne 0) { throw "CMake configuration failed" }
    cmake --build $BuildDir --config Release --parallel --target llama-server llama-cli
    if ($LASTEXITCODE -ne 0) { throw "llama.cpp compilation failed" }

    $Server = Get-ChildItem $BuildDir -Recurse -Filter "llama-server.exe" | Select-Object -First 1
    $Cli = Get-ChildItem $BuildDir -Recurse -Filter "llama-cli.exe" | Select-Object -First 1
    if (-not $Server -or -not $Cli) { throw "Compiled executables were not found below $BuildDir" }
    Copy-Item $Server.FullName (Join-Path $RuntimeDir "llama-server.exe") -Force
    Copy-Item $Cli.FullName (Join-Path $RuntimeDir "llama-cli.exe") -Force
}

if ($DownloadModel) {
    $Destination = Join-Path $ModelDir $ModelFile
    Write-Host "Downloading $ModelFile. The transfer resumes if a partial file exists."
    & curl.exe --fail --location --retry 5 --retry-delay 5 --continue-at - --output $Destination $ModelUrl
    if ($LASTEXITCODE -ne 0) { throw "Model download failed" }
}

$ServerPath = Join-Path $RuntimeDir "llama-server.exe"
$ModelPath = Join-Path $ModelDir $ModelFile
if ($BuildRuntime -and -not (Test-Path $ServerPath)) { throw "Missing runtime: $ServerPath" }
if ($DownloadModel -and -not (Test-Path $ModelPath)) { throw "Missing model: $ModelPath" }

if ((Test-Path $ServerPath) -and (Test-Path $ModelPath)) {
    Write-Host "Setup complete. Run: python run_server.py --open-browser"
} else {
    Write-Host "Requested stage complete. Run the other stage before starting Qwen."
}
