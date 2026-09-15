#!/usr/bin/env bash
# Build llama.cpp and download Qwen3-30B-A3B Q4_K_M entirely below this folder.
set -Eeuo pipefail
IFS=$'\n\t'

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SOURCE_DIR="$SCRIPT_DIR/build/llama.cpp"
readonly MODEL_DIR="$SCRIPT_DIR/models"
readonly RUNTIME_DIR="$SCRIPT_DIR/runtime"
readonly DOWNLOAD_DIR="$SCRIPT_DIR/downloads"
readonly LLAMA_CPP_REF="${LLAMA_CPP_REF:-b10621}"
readonly MODEL_FILE="${QWEN_MODEL_FILE:-Qwen3-30B-A3B-Q4_K_M.gguf}"
readonly MODEL_URL="${QWEN_MODEL_URL:-https://huggingface.co/Qwen/Qwen3-30B-A3B-GGUF/resolve/main/$MODEL_FILE?download=true}"
readonly JOBS="${JOBS:-$(getconf _NPROCESSORS_ONLN)}"
readonly CMAKE_VERSION="${CMAKE_VERSION:-3.31.6}"

BUILD_RUNTIME=1
DOWNLOAD_MODEL=1
PREFLIGHT_ONLY=0
if [[ ${1:-} == "--runtime-only" ]]; then DOWNLOAD_MODEL=0; shift; fi
if [[ ${1:-} == "--model-only" ]]; then BUILD_RUNTIME=0; shift; fi
if [[ ${1:-} == "--preflight" ]]; then PREFLIGHT_ONLY=1; BUILD_RUNTIME=0; DOWNLOAD_MODEL=0; shift; fi
if (($#)); then
  printf 'Usage: %s [--preflight|--runtime-only|--model-only]\n' "$0" >&2
  exit 2
fi

required_commands=(curl)
if ((BUILD_RUNTIME || PREFLIGHT_ONLY)); then
  required_commands+=(git c++ tar)
fi
for command_name in "${required_commands[@]}"; do
  command -v "$command_name" >/dev/null 2>&1 || {
    printf 'Missing required host command: %s\n' "$command_name" >&2
    printf 'No system packages are installed by this script.\n' >&2
    exit 1
  }
done

if ((PREFLIGHT_ONLY)); then
  if command -v cmake >/dev/null 2>&1; then
    printf 'Using host CMake: %s\n' "$(command -v cmake)"
  elif [[ $(uname -s) == Linux && $(uname -m) == x86_64 ]]; then
    printf 'Host CMake is absent; setup will download portable CMake %s locally.\n' "$CMAKE_VERSION"
  else
    printf 'CMake is absent and automatic bootstrap currently supports only Linux x86-64.\n' >&2
    exit 1
  fi
  printf 'Preflight passed. No files were downloaded or compiled.\n'
  exit 0
fi

mkdir -p "$SOURCE_DIR" "$MODEL_DIR" "$RUNTIME_DIR" "$DOWNLOAD_DIR"

CMAKE_BIN=""
if ((BUILD_RUNTIME)); then
  CMAKE_BIN="$(command -v cmake || true)"
fi
if ((BUILD_RUNTIME)) && [[ -z "$CMAKE_BIN" ]]; then
  [[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || {
    printf 'Automatic CMake bootstrap supports only Linux x86-64.\n' >&2
    exit 1
  }
  cmake_root="$DOWNLOAD_DIR/cmake-${CMAKE_VERSION}-linux-x86_64"
  cmake_archive="$DOWNLOAD_DIR/cmake-${CMAKE_VERSION}-linux-x86_64.tar.gz"
  if [[ ! -x "$cmake_root/bin/cmake" ]]; then
    curl --fail --location --retry 5 --retry-delay 3 \
      --output "$cmake_archive.part" \
      "https://github.com/Kitware/CMake/releases/download/v${CMAKE_VERSION}/cmake-${CMAKE_VERSION}-linux-x86_64.tar.gz"
    mv "$cmake_archive.part" "$cmake_archive"
    tar -xf "$cmake_archive" -C "$DOWNLOAD_DIR"
  fi
  CMAKE_BIN="$cmake_root/bin/cmake"
fi

if ((BUILD_RUNTIME)); then
  if [[ ! -d "$SOURCE_DIR/.git" ]]; then
    if [[ -e "$SOURCE_DIR" && -n "$(find "$SOURCE_DIR" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
      printf 'Source destination exists but is not a Git checkout: %s\n' "$SOURCE_DIR" >&2
      exit 1
    fi
    rmdir "$SOURCE_DIR" 2>/dev/null || true
    git clone https://github.com/ggml-org/llama.cpp.git "$SOURCE_DIR"
  fi
  git -C "$SOURCE_DIR" fetch --tags origin "$LLAMA_CPP_REF"
  git -C "$SOURCE_DIR" checkout --detach FETCH_HEAD
  "$CMAKE_BIN" -S "$SOURCE_DIR" -B "$SOURCE_DIR/build" \
    -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF
  "$CMAKE_BIN" --build "$SOURCE_DIR/build" --config Release -j "$JOBS" \
    --target llama-server llama-cli
  install -m 0755 "$SOURCE_DIR/build/bin/llama-server" "$RUNTIME_DIR/llama-server"
  install -m 0755 "$SOURCE_DIR/build/bin/llama-cli" "$RUNTIME_DIR/llama-cli"
fi

if ((DOWNLOAD_MODEL)); then
  printf 'Downloading %s (approximately 18.6 GB).\n' "$MODEL_FILE"
  curl --fail --location --retry 5 --retry-delay 5 --continue-at - \
    --output "$MODEL_DIR/$MODEL_FILE" "$MODEL_URL"
fi

if ((BUILD_RUNTIME)); then
[[ -x "$RUNTIME_DIR/llama-server" ]] || {
  printf 'llama-server is absent. Run %s --runtime-only\n' "$0" >&2
  exit 1
}
fi
if ((DOWNLOAD_MODEL)); then
[[ -s "$MODEL_DIR/$MODEL_FILE" ]] || {
  printf 'Model is absent. Run %s --model-only\n' "$0" >&2
  exit 1
}
fi

if [[ -x "$RUNTIME_DIR/llama-server" && -s "$MODEL_DIR/$MODEL_FILE" ]]; then
  printf '\nSetup complete. Start the browser server with:\n'
  printf '  python3 %s/run_server.py\n' "$SCRIPT_DIR"
else
  printf '\nRequested stage complete. Run the other stage before starting Qwen.\n'
fi
