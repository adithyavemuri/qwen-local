#!/usr/bin/env bash
# Build a pinned llama.cpp runtime and a selected GGUF below this folder.
set -Eeuo pipefail
IFS=$'\n\t'

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SOURCE_DIR="$SCRIPT_DIR/build/llama.cpp"
readonly MODEL_DIR="$SCRIPT_DIR/models"
readonly RUNTIME_DIR="$SCRIPT_DIR/runtime"
readonly DOWNLOAD_DIR="$SCRIPT_DIR/downloads"
readonly JOBS="${JOBS:-$(getconf _NPROCESSORS_ONLN)}"

BUILD_RUNTIME=1
DOWNLOAD_MODEL=1
PREFLIGHT_ONLY=0
MODEL_PRESET="${QWEN_MODEL_PRESET:-}"
stage=""
while (($#)); do
  case "$1" in
    --model)
      (($# >= 2)) || { printf 'Missing value for --model\n' >&2; exit 2; }
      MODEL_PRESET="$2"; shift 2 ;;
    --list-models) exec python3 "$SCRIPT_DIR/model_config.py" --list-models ;;
    --preflight|--runtime-only|--model-only)
      [[ -z "$stage" ]] || { printf 'Choose only one setup stage.\n' >&2; exit 2; }
      stage="$1"; shift ;;
    *) printf 'Usage: %s [--model PRESET] [--preflight|--runtime-only|--model-only|--list-models]\n' "$0" >&2; exit 2 ;;
  esac
done
case "$stage" in
  --preflight) PREFLIGHT_ONLY=1; BUILD_RUNTIME=0; DOWNLOAD_MODEL=0 ;;
  --runtime-only) DOWNLOAD_MODEL=0 ;;
  --model-only) BUILD_RUNTIME=0 ;;
esac
command -v python3 >/dev/null || { printf 'Python 3.10+ is required.\n' >&2; exit 1; }
tool_config() { python3 "$SCRIPT_DIR/model_config.py" --tool cmake "$@"; }
PINNED_CMAKE_VERSION="$(tool_config --field version)"
if [[ -n "${CMAKE_VERSION:-}" && "$CMAKE_VERSION" != "$PINNED_CMAKE_VERSION" ]]; then
  printf 'CMAKE_VERSION must match the verified tools.cmake pin in models.json (%s).\n' "$PINNED_CMAKE_VERSION" >&2
  exit 2
fi
readonly CMAKE_VERSION="$PINNED_CMAKE_VERSION"
config_arguments=()
if [[ -n "$MODEL_PRESET" ]]; then config_arguments=(--preset "$MODEL_PRESET"); fi
config() { python3 "$SCRIPT_DIR/model_config.py" "${config_arguments[@]}" "$@"; }
readonly MODEL_FILE="$(config --field filename)"
readonly MODEL_URL="$(config --field url)"
readonly MODEL_SIZE="$(config --field size_bytes)"
readonly LLAMA_CPP_REF="$(config --field llama_ref)"
readonly LLAMA_CPP_COMMIT="$(config --field llama_commit)"
# A failed command substitution inside 'readonly' otherwise masks its status.
[[ -n "$MODEL_FILE" && -n "$MODEL_URL" && -n "$LLAMA_CPP_REF" ]] || exit 2
printf 'Model: %s (%s bytes)\nRuntime: %s\n' "$MODEL_FILE" "$MODEL_SIZE" "$LLAMA_CPP_REF"

required_commands=(curl)
if ((BUILD_RUNTIME || PREFLIGHT_ONLY)); then
  required_commands+=(git c++ tar make)
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
  elif [[ -x "$DOWNLOAD_DIR/cmake-${CMAKE_VERSION}-linux-x86_64/bin/cmake" ]]; then
    printf 'Using previously downloaded portable CMake %s.\n' "$CMAKE_VERSION"
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
    if [[ ! -f "$cmake_archive" ]]; then
      curl --fail --location --silent --show-error --retry 5 --retry-delay 3 --continue-at - \
        --output "$cmake_archive.part" "$(tool_config --field url)"
      tool_config --verify "$cmake_archive.part"
      mv "$cmake_archive.part" "$cmake_archive"
    else
      tool_config --verify "$cmake_archive"
    fi
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
    git -C "$SOURCE_DIR" init
    git -C "$SOURCE_DIR" remote add origin https://github.com/ggml-org/llama.cpp.git
  fi
  [[ -z "$(git -C "$SOURCE_DIR" status --porcelain --untracked-files=no)" ]] || {
    printf 'Refusing to replace modified runtime source files.\n' >&2; exit 1;
  }
  git -C "$SOURCE_DIR" fetch --depth 1 origin "$LLAMA_CPP_REF"
  git -C "$SOURCE_DIR" checkout --detach FETCH_HEAD
  if [[ -n "$LLAMA_CPP_COMMIT" && "$(git -C "$SOURCE_DIR" rev-parse HEAD)" != "$LLAMA_CPP_COMMIT" ]]; then
    printf 'Runtime source does not match the pinned commit.\n' >&2; exit 1
  fi
  "$CMAKE_BIN" -S "$SOURCE_DIR" -B "$SOURCE_DIR/build" \
    -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DGGML_BACKEND_DL=OFF \
    -DGGML_CUDA=OFF -DGGML_NATIVE=ON -DLLAMA_BUILD_TESTS=OFF
  "$CMAKE_BIN" --build "$SOURCE_DIR/build" --config Release -j "$JOBS" \
    --target llama-server llama-cli
  install -m 0755 "$SOURCE_DIR/build/bin/llama-server" "$RUNTIME_DIR/llama-server"
  install -m 0755 "$SOURCE_DIR/build/bin/llama-cli" "$RUNTIME_DIR/llama-cli"
  config --write-runtime-manifest
fi

if ((DOWNLOAD_MODEL)); then
  if [[ -f "$MODEL_DIR/$MODEL_FILE" ]]; then
    config --verify "$MODEL_DIR/$MODEL_FILE"
  else
    printf 'Downloading %s. Partial transfers resume; SHA-256 is checked before use.\n' "$MODEL_FILE"
    curl --fail --location --silent --show-error --retry 5 --retry-delay 5 --continue-at - \
      --output "$MODEL_DIR/$MODEL_FILE.part" "$MODEL_URL"
    config --verify "$MODEL_DIR/$MODEL_FILE.part"
    mv "$MODEL_DIR/$MODEL_FILE.part" "$MODEL_DIR/$MODEL_FILE"
  fi
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
  printf '  python3 %s/run_server.py --preset %s\n' "$SCRIPT_DIR" "$(config --field preset)"
else
  printf '\nRequested stage complete. Run the other stage before starting Qwen.\n'
fi
