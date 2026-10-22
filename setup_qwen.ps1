[CmdletBinding()]
param(
    [switch]$Preflight,
    [switch]$RuntimeOnly,
    [switch]$ModelOnly,
    [string]$ModelPreset = ""
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

Require-Command python "Install Python 3.10+ and open a new terminal."
Require-Command curl.exe "Use a supported Windows 10/11 installation or install curl."
if ($BuildRuntime) {
    Require-Command git "Install Git for Windows and open a new terminal."
    Require-Command cmake "Install Visual Studio 2022 C++ CMake tools."
    Require-Command cl.exe "Run this script from Developer PowerShell for VS 2022."
}
$ConfigArguments = @((Join-Path $ProjectDir "model_config.py"))
if ($ModelPreset) { $ConfigArguments += @("--preset", $ModelPreset) }
$ConfigJson = & python @ConfigArguments
if ($LASTEXITCODE -ne 0) { throw "Invalid model configuration" }
$Config = $ConfigJson | ConvertFrom-Json
$LlamaRef = $Config.llama_ref
$ModelFile = $Config.filename
$ModelUrl = $Config.url

Write-Host "Windows Qwen preflight"
Write-Host "  Project: $ProjectDir"
Write-Host "  Architecture: $env:PROCESSOR_ARCHITECTURE"
Write-Host "  llama.cpp revision: $LlamaRef"
Write-Host "  Model: $ModelFile ($($Config.size_bytes) bytes)"
Write-Host "  All generated files stay under this project directory."
if ($Preflight) {
    Write-Host "Preflight passed. Nothing was downloaded or compiled."
    return
}

New-Item -ItemType Directory -Force -Path $ModelDir, $RuntimeDir, $DownloadDir | Out-Null

if ($BuildRuntime) {
    if (-not (Test-Path (Join-Path $SourceDir ".git"))) {
        if (Test-Path $SourceDir) {
            $items = @(Get-ChildItem -Force $SourceDir)
            if ($items.Count -gt 0) { throw "Source destination exists but is not a Git checkout: $SourceDir" }
        }
        New-Item -ItemType Directory -Force -Path $SourceDir | Out-Null
        git -C $SourceDir init
        if ($LASTEXITCODE -ne 0) { throw "git init failed" }
        git -C $SourceDir remote add origin https://github.com/ggml-org/llama.cpp.git
        if ($LASTEXITCODE -ne 0) { throw "git remote failed" }
    }
    $Dirty = @(git -C $SourceDir status --porcelain '--untracked-files=no')
    if ($LASTEXITCODE -ne 0) { throw "git status failed" }
    if ($Dirty.Count) { throw "Refusing to replace modified runtime source files." }
    git -C $SourceDir fetch --depth 1 origin $LlamaRef
    if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }
    git -C $SourceDir checkout --detach FETCH_HEAD
    if ($LASTEXITCODE -ne 0) { throw "git checkout failed" }
    $ActualCommit = git -C $SourceDir rev-parse HEAD
    if ($LASTEXITCODE -ne 0) { throw "git rev-parse failed" }
    if ($Config.llama_commit -and $ActualCommit -ne $Config.llama_commit) {
        throw "Runtime source does not match the pinned commit."
    }

    $BuildDir = Join-Path $SourceDir "build-windows"
    cmake -S $SourceDir -B $BuildDir -A x64 '-DBUILD_SHARED_LIBS=OFF' '-DGGML_BACKEND_DL=OFF' '-DGGML_CUDA=OFF' '-DLLAMA_BUILD_TESTS=OFF' '-DLLAMA_OPENSSL=OFF'
    if ($LASTEXITCODE -ne 0) { throw "CMake configuration failed" }
    cmake --build $BuildDir --config Release --parallel --target llama-server llama-cli
    if ($LASTEXITCODE -ne 0) { throw "llama.cpp compilation failed" }

    $Server = Get-ChildItem $BuildDir -Recurse -Filter "llama-server.exe" | Select-Object -First 1
    $Cli = Get-ChildItem $BuildDir -Recurse -Filter "llama-cli.exe" | Select-Object -First 1
    if (-not $Server -or -not $Cli) { throw "Compiled executables were not found below $BuildDir" }
    Copy-Item $Server.FullName (Join-Path $RuntimeDir "llama-server.exe") -Force
    Copy-Item $Cli.FullName (Join-Path $RuntimeDir "llama-cli.exe") -Force
    & python @ConfigArguments --write-runtime-manifest
    if ($LASTEXITCODE -ne 0) { throw "Runtime manifest verification failed" }
}

if ($DownloadModel) {
    $Destination = Join-Path $ModelDir $ModelFile
    if (Test-Path $Destination) {
        & python @ConfigArguments --verify $Destination
        if ($LASTEXITCODE -ne 0) { throw "Existing model failed verification; it was not replaced." }
    } else {
        $Partial = "$Destination.part"
        Write-Host "Downloading $ModelFile. Partial transfers resume; SHA-256 is checked before use."
        & curl.exe --fail --location --retry 5 --retry-delay 5 --continue-at '-' --output $Partial $ModelUrl
        if ($LASTEXITCODE -ne 0) { throw "Model download failed" }
        & python @ConfigArguments --verify $Partial
        if ($LASTEXITCODE -ne 0) { throw "Downloaded model failed verification." }
        Move-Item $Partial $Destination
    }
}

$ServerPath = Join-Path $RuntimeDir "llama-server.exe"
$ModelPath = Join-Path $ModelDir $ModelFile
if ($BuildRuntime -and -not (Test-Path $ServerPath)) { throw "Missing runtime: $ServerPath" }
if ($DownloadModel -and -not (Test-Path $ModelPath)) { throw "Missing model: $ModelPath" }

if ((Test-Path $ServerPath) -and (Test-Path $ModelPath)) {
    Write-Host "Setup complete. Run: python run_server.py --preset $($Config.preset) --open-browser"
} else {
    Write-Host "Requested stage complete. Run the other stage before starting Qwen."
}
