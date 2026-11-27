#!/bin/sh
# NbAiLab nb-whisper-large on the host GPU. Compose reaches it on port 8082.
set -eu

root="${WHISPER_HOME:-$HOME/.local/share/logoskittens/whisper}"
port="${WHISPER_PORT:-8082}"
src="$root/src"
model="$root/ggml-nb-whisper-large.bin"
vad="$root/ggml-silero-v6.2.0.bin"
control_port="${WHISPER_CONTROL_PORT:-8083}"

mkdir -p "$root"

if ! command -v cmake >/dev/null 2>&1 || ! command -v git >/dev/null 2>&1; then
  echo "host whisper needs cmake and git" >&2
  exit 1
fi

has_cuda() {
  command -v nvidia-smi >/dev/null 2>&1 || return 1
  command -v nvcc >/dev/null 2>&1 || return 1
  nvidia-smi >/dev/null 2>&1 || return 1
  return 0
}

has_vulkan_gpu() {
  command -v vulkaninfo >/dev/null 2>&1 || return 1
  vulkaninfo --summary 2>/dev/null | grep -E -q 'PHYSICAL_DEVICE_TYPE_(DISCRETE|INTEGRATED)_GPU' || return 1
  return 0
}

case "$(uname -s)" in
  Darwin)
    backend=metal
    jobs="$(sysctl -n hw.ncpu)"
    ;;
  Linux)
    jobs="$(nproc)"
    if has_cuda; then
      backend=cuda
    else
      if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1 \
        && ! command -v nvcc >/dev/null 2>&1; then
        echo "NVIDIA GPU found; nvcc is not on PATH, so CUDA was not selected" >&2
      fi
      if has_vulkan_gpu; then
        backend=vulkan
      else
        backend=cpu
      fi
    fi
    ;;
  *)
    echo "This launcher is for macOS and Linux. On Windows run scripts/host_whisper.ps1" >&2
    exit 1
    ;;
esac

echo "whisper backend: $backend"
if [ "$backend" = "cpu" ]; then
  echo "GPU is not in use"
fi

build="$src/build-$backend"
server="$build/bin/whisper-server"

if [ ! -x "$server" ]; then
  if [ ! -d "$src/.git" ]; then
    git clone --depth 1 https://github.com/ggml-org/whisper.cpp.git "$src"
  fi
  if [ "$backend" = "cpu" ]; then
    cmake -S "$src" -B "$build" \
      -DCMAKE_BUILD_TYPE=Release \
      -DWHISPER_BUILD_SERVER=ON
  elif [ "$backend" = "metal" ]; then
    cmake -S "$src" -B "$build" \
      -DCMAKE_BUILD_TYPE=Release \
      -DGGML_METAL=ON \
      -DWHISPER_BUILD_SERVER=ON
  elif [ "$backend" = "cuda" ]; then
    cmake -S "$src" -B "$build" \
      -DCMAKE_BUILD_TYPE=Release \
      -DGGML_CUDA=ON \
      -DWHISPER_BUILD_SERVER=ON
  else
    cmake -S "$src" -B "$build" \
      -DCMAKE_BUILD_TYPE=Release \
      -DGGML_VULKAN=ON \
      -DWHISPER_BUILD_SERVER=ON
  fi
  cmake --build "$build" -j"$jobs" --target whisper-server
fi

if [ ! -f "$model" ]; then
  if [ -f /tmp/ggml-nb-whisper-large.bin ]; then
    cp /tmp/ggml-nb-whisper-large.bin "$model"
  else
    partial="$model.partial"
    curl -L --fail -o "$partial" \
      https://huggingface.co/NbAiLab/nb-whisper-large/resolve/main/ggml-model.bin \
      || { rm -f "$partial"; exit 1; }
    mv "$partial" "$model"
  fi
fi

script_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
if command -v python3 >/dev/null 2>&1; then
  python=python3
elif command -v python >/dev/null 2>&1; then
  python=python
else
  echo "host whisper needs python3 to read .env_recognition" >&2
  exit 1
fi
eval "$("$python" "$script_dir/recognition_env.py" --shell)"
english="$root/$recognition_file"

if [ ! -f "$english" ]; then
  partial="$english.partial"
  curl -L --fail -o "$partial" "$recognition_url" \
    || { rm -f "$partial"; exit 1; }
  mv "$partial" "$english"
fi

if [ ! -f "$vad" ]; then
  bash "$src/models/download-vad-model.sh" silero-v6.2.0 "$root"
fi

# Other live packs (Ukrainian) name their weight and its url in config/languages.
set --
extra=$("$python" "$script_dir/extra_weights.py")
if [ -n "$extra" ]; then
  while read -r extra_language extra_file extra_url; do
    weight="$root/$extra_file"
    if [ ! -f "$weight" ]; then
      echo "downloading $extra_file for $extra_language" >&2
      partial="$weight.partial"
      curl -L --fail -o "$partial" "$extra_url" \
        || { rm -f "$partial"; exit 1; }
      mv "$partial" "$weight"
    fi
    set -- "$@" --model "$extra_language=$weight"
  done <<EOF
$extra
EOF
fi

exec "$python" "$script_dir/whisper_supervisor.py" "$@" \
  --server "$server" \
  --nb-model "$model" \
  --en-model "$english" \
  --en-name "$recognition_model" \
  --vad "$vad" \
  --port "$port" \
  --control-port "$control_port" \
  --threads "$recognition_threads"
