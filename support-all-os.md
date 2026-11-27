# Three operating systems

The greeting loop runs on macOS, Ubuntu, and Windows. Speech recognition and the local model use the GPU of that machine. The hub, the page, Piper, and the protobuf contract stay one codebase.

The host launcher selects the backend and prints it before the server listens. macOS builds Metal. Linux and Windows use CUDA when `nvidia-smi` and `nvcc` work, otherwise Vulkan when a Vulkan GPU is present, otherwise CPU. A CPU start prints that the GPU is not in use. Each backend has its own build directory (`build-metal`, `build-cuda`, `build-vulkan`, `build-cpu`), so a Metal binary is not reused after an OS change.

## One stack

Compose always starts the same three Linux containers:

| Process | Where it runs | GPU |
| --- | --- | --- |
| `whisper-server` (`nb-whisper-large`, Silero VAD, language `no`, port 8082) | Host | Yes |
| Ollama `qwen3:8b` (port 11434) | Host | Yes |
| `audio-engine` (Piper, proxies `/transcribe` to the host) | Container | No |
| `cognitive-hub` | Container | No |
| `virtual-stage` | Container | No |

The audio container calls `WHISPER_URL` (`http://host.docker.internal:8082/inference`). The hub calls Ollama at `http://host.docker.internal:11434`. Compose already maps `host.docker.internal` to the host on Linux and on Docker Desktop. Those two URLs do not change per OS.

Start the recognizer and Ollama before `docker compose up`. The audio health check stays red, and the hub does not start, until port 8082 answers.

The model file is the same on every OS: NbAiLab `ggml-model.bin` stored as `ggml-nb-whisper-large.bin`, plus `ggml-silero-v6.2.0.bin`. The server flags stay `-l no -nt --host 0.0.0.0 --port 8082 --vad --vad-min-speech-duration-ms 100 --vad-min-silence-duration-ms 400 --vad-speech-pad-ms 300 -vm <silero>`.

## GPU choice

The launcher picks one backend and prints the name before it listens.

| Machine | Backend | CMake flag |
| --- | --- | --- |
| macOS | Metal | `-DGGML_METAL=ON` |
| NVIDIA GPU (Ubuntu or Windows) | CUDA | `-DGGML_CUDA=ON` |
| AMD or Intel GPU | Vulkan | `-DGGML_VULKAN=ON` |
| No toolkit and no Vulkan device | CPU | neither GPU flag |

Order on Linux and Windows: CUDA when `nvidia-smi` works and `nvcc` is on `PATH`, otherwise Vulkan when a Vulkan device is present, otherwise CPU. A CPU start must print that the GPU is not in use. macOS always builds Metal.

Ollama does not use this choice. Its installer brings its own GPU runtime. Installing Ollama does not provide `nvcc`, and a CUDA whisper build does not configure Ollama.

## macOS

This is the current machine. Leave the behavior as it is.

- Docker Desktop. The Apple GPU is not visible inside a container, so recognition stays on the host.
- `./scripts/host_whisper.sh` clones whisper.cpp, builds with Metal, downloads the two weights, and execs `whisper-server`.
- Ollama is the host app. It uses Metal on its own.
- Job count for the compile stays `sysctl -n hw.ncpu`.

A copy of `~/.local/share/logoskittens/whisper` from this Mac must not be reused on another OS. The script treats an existing `whisper-server` as already built and will not cross-compile.

## Ubuntu with a GPU

Same Compose file. `./scripts/host_whisper.sh` clones whisper.cpp, builds `whisper-server` for the backend it selected, downloads the two weights, and listens on port 8082.

Packages, once: `build-essential`, `cmake`, `git`, `curl`, `ca-certificates`, `ffmpeg`. ffmpeg is for the audio container's own image, not for the host script. The host script needs cmake and git.

NVIDIA:

- Driver new enough that `nvidia-smi` prints the GPU.
- CUDA toolkit so `nvcc` is on `PATH`. The whisper.cpp build links cuBLAS at compile time. The running server then needs the matching CUDA driver libraries, which the driver package provides.
- CMake: `-DGGML_CUDA=ON -DWHISPER_BUILD_SERVER=ON -DCMAKE_BUILD_TYPE=Release`. Let CMake target the GPU that is installed. Do not pass `-DGGML_METAL=ON`.
- Compile jobs: `nproc`.

AMD or Intel:

- Vulkan loader and `glslc` (shaderc). `vulkaninfo` must list the device.
- CMake: `-DGGML_VULKAN=ON` and the same server flag. Skip CUDA.

CPU fallback uses the same server binary with no GPU flag. Recognition still works. It will not match the 0.11 s Metal time measured on this M4 Pro.

Ollama: the official Linux install (`https://ollama.com/install.sh`). On NVIDIA it selects CUDA by itself. Pull `qwen3:8b` and leave the process on port 11434. `LLM_BASE_URL` stays `http://host.docker.internal:11434/v1`. The hub already strips `/v1` and posts to `/api/chat`.

The Linux service listens on `127.0.0.1`. The hub connects through the Docker bridge, so set `OLLAMA_HOST=0.0.0.0:11434` in the systemd unit and restart Ollama.

Firewall: if `ufw` is denying forwarded traffic, a container's connection to `host.docker.internal:8082` fails while `curl` on the host succeeds. Allow that port from the Docker bridge, or confirm from inside `audio-engine` that `WHISPER_URL` returns a page.

Then, from the repo root:

```bash
./scripts/host_whisper.sh
docker compose up --build
```

## Windows

Docker Desktop with the WSL2 engine. Containers stay the Linux images from this repo. Recognition and Ollama run as Windows processes so Docker's `host.docker.internal` reaches them. That is the same shape as the Mac.

Do not document a second layout where Compose runs inside a separate Ubuntu WSL distro. A person who wants that follows the Ubuntu section inside that distro.

Launcher: `scripts/host_whisper.ps1`. It follows the same backend rule and runs `build-<backend>\bin\Release\whisper-server.exe`.

- Tools: Git, CMake, and the Visual Studio 2022 Build Tools (Desktop development with C++). NVIDIA also needs the CUDA toolkit (`nvcc` on `PATH`). AMD or Intel needs the Vulkan SDK so `vulkaninfo` lists a device.
- CMake generator: the Visual Studio generator, Release config, `-DWHISPER_BUILD_SERVER=ON`, plus `-DGGML_CUDA=ON` or `-DGGML_VULKAN=ON` by the rule above.
- Binary: `build/bin/Release/whisper-server.exe`. Run it with the same flags as the shell script. Weights live under `%LOCALAPPDATA%\logoskittens\whisper`.
- First bind to port 8082 may raise a Windows Firewall prompt. Private networks must be allowed, or the container cannot connect.

Ollama: the Windows installer from ollama.com. It listens on 11434 and uses CUDA when an NVIDIA driver is present. Pull `qwen3:8b`. No hub change.

Start order is a PowerShell window left open on the recognizer, Ollama running, then `docker compose up --build` in the repo.

## Launchers

- `scripts/host_whisper.sh` on macOS and Ubuntu. Darwin keeps Metal and `sysctl`. Linux uses `nproc` and the CUDA, then Vulkan, then CPU rule. The download URLs, the port, the language, and the VAD flags stay.
- `scripts/host_whisper.ps1` on Windows. Same rule, Visual Studio 2022 Release build, `whisper-server.exe`. Weights live under `%LOCALAPPDATA%\logoskittens\whisper`. The Silero file is the same Hugging Face URL the shell script's downloader uses.
- README quick start and `AGENTS.md` list both starts. The recognizer uses the host GPU.
- The audio container, Compose, the hub, and the page are unchanged.

## Check on each OS

1. The launcher prints the backend (`metal`, `cuda`, `vulkan`, or `cpu`).
2. `curl http://127.0.0.1:8082/` answers before Compose starts.
3. `http://127.0.0.1:8081/health` reports `whisper: true` and `voice: true`.
4. A synthesized "Hva skal jeg gjøre?" transcribed through the audio engine returns that sentence, with language `no`.
5. The CLI text turn `Hei` returns two actor replies.
6. The page at `http://localhost:5174` plays a short greeting. On Windows this is Docker Desktop's localhost, same ports.

Record the backend name and the transcribe time next to the Mac numbers (warm Metal call 0.11 s, CPU-in-Docker 0.82 s) once an Ubuntu GPU machine and a Windows GPU machine have been run. Do not invent those times here.

## Out of scope

- A CUDA or Vulkan build baked into the Piper image. macOS Docker cannot see the GPU, and that would fork the image.
- A second Compose file per OS.
- Stages 10 and 11.
- Moving Ollama into Compose.
- ROCm as its own backend. Vulkan covers AMD on both Ubuntu and Windows. Add ROCm only if a measured Vulkan run on a target AMD GPU misses the recognizer budget.
