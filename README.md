# LogosKittens - Robots friendly conversation partner

Current list of supported languages: English, Ukrainian, German, Hebrew, Norwegian.

LogosKittens is a dual-interface, open-source voice client for the polyglot platform [www.logoscat.com](https://www.logoscat.com).

<img src="docs/images/floating-kitten.png" alt="A robot kitten floating in space" width="400">

**Why dual-interface?** It is an experimental system that goes beyond a human simply talking to a server to practice languages. Built as a robot-oriented platform, it allows [N robots to connect and collaborate](https://www.youtube.com/watch?v=mm5qdjpUDf0) on a shared scenario — in this case, helping you learn a language.

You can use the web interface to talk directly to your Mac, Linux, or Windows machine, or use the multi-bot interface to converse with physical robots that take on distinct roles, such as a conversation partner and a teacher.

Everything links to your logoscat.com account (it is an option, this works without any account too), allowing you to use the texts you have translated on the platform as grounding material. This means you can practice speaking directly in the context of the exact material you just translated and studied.

## Web Interface

![Web interface](docs/images/web-mode.png)

## Bot-Net Interface

![Bot-Net interface](docs/images/bot-mode.png)

## Use your logoscat materials

You can bring in the sessions you worked on at logoscat.com, so the conversation is about concrete subjects that interest you. New to LogosCat? Read [how to get started with LogosCat](https://portal.logoscat.com/how-to-get-started-with-logoscat/).

![Workspace sessions from LogosCat](docs/images/workspace-sessions.png)

## Example Interaction with bots

[![Example interaction with bots](https://img.youtube.com/vi/mm5qdjpUDf0/hqdefault.jpg)](https://www.youtube.com/watch?v=mm5qdjpUDf0)

https://www.youtube.com/watch?v=mm5qdjpUDf0

**Cognitive Edge & Robot Middleware for free conversation and embodied agents.**

The live talk is specified in [`free_conv.md`](free_conv.md). LogosKittens decouples high-level cognitive reasoning from execution media. The same primitives (`Situation`, `Task`, `Actor`, `GroupSolution`, `ElementSolution`) drive both screen avatars and physical robots. The system runs locally by default (Docker, Whisper.cpp, Piper TTS, SQLite) with an OpenAI-compatible LLM abstraction that supports local models and Grok.

## Example Robot Extension

[`lk_body`](https://github.com/ganapetya/masha/tree/main/ros2_ws/src/lk_body) is the robot side for Masha, a hexapod on a Jetson. It dials the hub's `/players` socket, records the human on the robot's microphone, plays the reply on its speaker, and runs the poses the hub names. Use it as the pattern for connecting another robot.

## Models

Some parts always run on your own machine, some run locally by default, and some call a remote model by default.

| Part | Default | Where |
| --- | --- | --- |
| Speech recognition | whisper.cpp (`small.en`; `nb-whisper-large` for Norsk; `large-v3-turbo` for Ukrainian) | Local, on the host GPU |
| Voice | Piper TTS | Local, in Docker |
| Buddy's replies and the lesson subject | Ollama `qwen3:8b` | Local. Set `LLM_BACKEND=grok` or `openai` to use Grok or OpenAI instead |
| Bob (buddy steering), Rob (teacher corrections), Wren (games) | Grok `grok-4.7` | Remote, xAI or OpenAI. Needs `XAI_API_KEY` or `OPENAI_API_KEY` |
| Prompt training: judge and proposer | Grok `grok-4.7` | Remote, set in `.env_training` |

Every remote part can use Grok or OpenAI. Open Settings, **Models** tab (`http://localhost:5174/#/settings/models`) to paste the keys and pick a provider, model, and think level for the buddy, Bob, Rob, and Wren. Values in `.env` are the defaults; a value saved there wins until you press Reset to .env. Keys stay on the hub.

With no xAI or OpenAI key, free speech still runs fully local: Bob and Rob are skipped, so Savelij makes no corrections, and the games that need Wren are not available. See [Set it up right](#set-it-up-right) for the settings.

## Quick Start

Speech recognition and Ollama run on the host so they can use the GPU. Compose starts Piper, the hub, and the page. Start Ollama and the recognizer first, and leave the recognizer terminal open. Compose does not start either one.

From the repo root:

```bash
cp .env.example .env
```

The default is `LLM_BACKEND=local` and `LLM_MODEL=qwen3:8b`. Leave `XAI_API_KEY` empty unless `LLM_BACKEND=grok`.

The recognizer prints `whisper backend: metal`, `cuda`, `vulkan`, or `cpu` before it listens on port 8082. macOS always builds Metal. Linux and Windows use CUDA when `nvidia-smi` and `nvcc` are available, otherwise Vulkan when a Vulkan GPU is present, otherwise CPU. A CPU start prints `GPU is not in use`. The first start compiles whisper.cpp, downloads the English weight named in `.env_recognition` (default `small.en`), and keeps `nb-whisper-large` for Norsk. Language changes in the page restart that one process through port 8083. Both weights stay on disk, and only one is loaded.

On macOS, Linux, and Windows, work in the browser at http://localhost:5174/. The hub is http://localhost:8090, the audio engine is http://localhost:8081, and the recognizer is http://localhost:8082. `http://127.0.0.1:8081/health` reports `"whisper": true` and `"voice": true` when both sides are up.

### macOS

Install Docker Desktop, Ollama, CMake, and Git. Pull the model:

```bash
ollama pull qwen3:8b
```

```bash
./scripts/host_whisper.sh
docker compose up --build
```

Work in the browser at http://localhost:5174/.

### Ubuntu

Install Docker Engine with the Compose plugin, plus `build-essential`, `cmake`, `git`, and `curl`. An NVIDIA GPU also needs a driver (`nvidia-smi` prints the card) and the CUDA toolkit (`nvcc` on `PATH`). An AMD or Intel GPU needs the Vulkan loader, `glslc`, and a device listed by `vulkaninfo`.

Ubuntu often installs Docker as a Snap (`which docker` prints `/snap/bin/docker`). The daemon can be running and Compose still fails immediately:

```text
permission denied while trying to connect to the docker API at unix:///var/run/docker.sock
```

That message is the socket, not a Compose or build error. The Snap listens on `/var/run/docker.sock` with mode `0660`. If no `docker` group existed when the Snap started, the socket is owned by `root:root`, so only root can open it. A normal user is refused even though `snap services docker` shows `docker.dockerd` active. `ls -l /var/run/docker.sock` then shows `srw-rw---- 1 root root`.

Create the group, join it, and restart the Snap so it recreates the socket as `root:docker`:

```bash
sudo addgroup --system docker
sudo adduser "$USER" docker
sudo snap disable docker
sudo snap enable docker
```

The shell you already have open does not gain the new group. Log out and back in, or run `newgrp docker` and start Compose from that shell. `id` should list `docker`, and `ls -l /var/run/docker.sock` should show `srw-rw---- 1 root docker`. Do not use `sudo docker compose` as the workaround. It connects once and leaves root-owned files in the project.

If Docker Engine came from apt, the `docker` group and a `root:docker` socket are usually already there. The same error only means your user is not in `docker`. Add the user, start a new login, and skip the Snap restart.

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/override.conf >/dev/null <<'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF
sudo systemctl daemon-reload
sudo systemctl restart ollama
ollama pull qwen3:8b
```

Ollama on Linux listens on `127.0.0.1` until that override. The hub reaches the host through the Docker bridge, so the override is required. If `ufw` is on and the audio health check stays at `"whisper": false` while `curl http://127.0.0.1:8082/` works on the host, allow ports 8082 and 8083 from the Docker bridge. Port 8083 is the language switch.

```bash
./scripts/host_whisper.sh
docker compose up --build
```

Work in the browser at http://localhost:5174/.

### Windows

Install Docker Desktop with the WSL2 engine, Git, CMake, and the Visual Studio 2022 Build Tools (Desktop development with C++). An NVIDIA GPU also needs the CUDA toolkit (`nvcc` on `PATH`). An AMD or Intel GPU needs the Vulkan SDK (`vulkaninfo` lists the device). Install Ollama from https://ollama.com and pull the model in PowerShell:

```powershell
ollama pull qwen3:8b
```

Leave the recognizer running in its own window. Allow the Windows Firewall prompt for port 8082 on private networks.

```powershell
.\scripts\host_whisper.ps1
docker compose up --build
```

If execution policy blocks the script:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\host_whisper.ps1
```

Work in the browser at http://localhost:5174/.

### Check from the host

With the Python package installed (`python3 -m venv .venv && .venv/bin/pip install -e 'cognitive-hub[dev]'`):

```bash
PYTHONPATH=cognitive-hub/src:shared/python .venv/bin/python -m logoskittens.cli --text "The fjords were quiet." --hub ws://localhost:8090/ws
./scripts/check_audio.sh
```

## Talk in the browser

The page is one endless talk with Buddy about a raw material. The first material is "Vacation in Norway" (tunnels and fjords). The Talk panel lists English, Norsk, Українська, Deutsch, and עברית. Choosing עברית mirrors the page right to left. A click starts a new talk in that language.

From the repo root, start three things and leave the first two running:

```bash
ollama pull qwen3:8b
./scripts/host_whisper.sh
docker compose up --build
```

On Windows the recognizer is `.\scripts\host_whisper.ps1`. Copy `.env.example` to `.env` once. The default buddy is local `qwen3:8b`. Set `XAI_API_KEY` only when `LLM_BACKEND=grok`.

Open http://localhost:5174.

- The theme is under the title. On a phone, Talk opens the material list.
- The mode switch starts on Web mode. Hold Speak, then release, and the browser records and plays the reply. Botnet mode is the robot face. Or type a line and press Send. That works in both modes.
- Buddy answers once. The talk does not end. Say another line.
- Reload the page. The same log comes back.
- The Buddy list is Peter or Mary. Peter is the default. Choosing the other person starts a new talk in that voice.
- Reset conversation drops this talk, builds the subject again from the raw material, keeps the buddy you are already on, and starts empty.
- Choosing another raw material starts a new session.
- BOB watches the talk after every third buddy line and may store one short steer for the next local replies. Its settings are `config/bob.json`, separate from `LLM_BACKEND`. The shipped backend is xAI with `XAI_API_KEY` (or `BOB_API_KEY`). The steer follows that buddy's character and a nearby subject. The buddy answers what was said, then uses the new part of the steer. A theme word already in the talk does not count. While QA is on, `altered by BOB` shows only when that new part was spoken, then `Suggested alteration:`. A steer still waiting shows `Next suggestion:`. QA is off until you turn it on.

Hub: http://localhost:8090. Audio: http://localhost:8081. Recognizer: http://localhost:8082. `http://127.0.0.1:8081/health` reports `"whisper": true` and `"voice": true` when both sides are up.

The virtual-stage image does not mount source. After a page change, rebuild it:

```bash
docker compose build virtual-stage && docker compose up -d --no-deps virtual-stage
```

## Talk with Masha

Botnet mode is the robot face. Turn the switch to Botnet mode. Masha is the client. She hears from the Speak button and plays the reply on her speaker. The page shows the words and does not play the sound. Web mode, the switch off, talks in the browser instead and does not need her.

Start the server on this machine first, and leave both running:

```bash
./scripts/host_whisper.sh
docker compose up --build
```

On Windows the recognizer is `.\scripts\host_whisper.ps1`. Copy `.env.example` to `.env` once. Open http://localhost:5174 and turn host mode on. The page shows the dial URL only while host mode is on. It is `ws://<this-machine-lan-address>:8090/players`.

On Masha, bringup is already running. Do not start a second one. Enter LogosKittens mode:

```bash
/home/ubuntu/ros2_ws/src/lk_body/deploy/lk_bot_mode enter
```

She dials `MASHA_HUB_WS` from `/home/ubuntu/ros2_ws/src/lk_body/.env`. That value is the dial URL from the page, the address she can reach. This machine's address changes. When it does, edit that one line and run `enter` again. The player list shows Masha Ready.

To talk, hold Speak for the whole sentence, then release. The microphone stays open for one second after you let go, so the last word is kept. A click is not a turn. One hold is one reply. Choosing Mary or Peter starts a new talk. A reload keeps the buddy you were on. Reset starts a new talk and keeps that buddy.

A suggestion can name one mimic: agreement, disagreement, frustration, or curiosity. With QA on, the BOB card shows `Mimic:` under the suggestion. She speaks first. The mimic runs after the voice, once. The next reply does not repeat it.

Leave LogosKittens mode when you are done. That stops her client and brings the keyword voice launch back. Bringup stays up.

```bash
/home/ubuntu/ros2_ws/src/lk_body/deploy/lk_bot_mode leave
```

## Change the recognizer

Speech recognition does not use the buddy model. Edit `.env_recognition`. If that file is missing, copy `.env_recognition.example`. The comments list every whisper.cpp weight. `RECOGNITION_MODEL` is the one that loads. The default is `small.en`, one step up from `base.en`.

Restart the recognizer after a change. The next start downloads a missing weight and leaves the old file on disk.

```bash
./scripts/host_whisper.sh
```

On Windows: `.\scripts\host_whisper.ps1`.

## Use Google voice and recognition

Optional. Click Settings in the page header. It opens http://localhost:5174/#/settings in a new tab. Paste a Google Cloud API key, restricted to Text-to-Speech and Speech-to-Text, or a service-account JSON. Then turn on Google voice, Google recognition, or both, and pick a man's, a woman's, and Savelij's voice per language. The settings stay on this hub and need no LogosCat account. When a Google voice call fails, Piper speaks that line.

## Set it up right

This chapter covers where each setting lives, what hardware the local models need, and how to make remote models answer fast.

### Where settings live

| What | Where | Notes |
| --- | --- | --- |
| Buddy model, keys, Bob, Rob, Wren defaults | `.env` (copy from `.env.example`) | Read when the hub starts. Recreate the hub after an edit: `docker compose up -d --no-deps cognitive-hub`. |
| Recognizer weight for English | `.env_recognition` (copy from `.env_recognition.example`) | Restart `./scripts/host_whisper.sh` after an edit. |
| Prompt training models | `.env_training` (copy from `.env_training.example`) | Training only. Practice never reads it. |
| Provider, model, and think level per part; xAI and OpenAI keys | Settings page, **Models** tab (`http://localhost:5174/#/settings/models`) | Applies from the next call, no restart. A value saved here wins over `.env` until you press **Reset to .env**. |
| Google voice and recognition, voices per language | Settings page, **Speech** tab (`http://localhost:5174/#/settings`) | Optional. Without it, Piper speaks and whisper hears. |
| Source and target languages | Talk panel, **Languages** | Connected to LogosCat, they come from your LogosCat settings ("From LogosCat"). Disconnected, your own choice ("Your choice"). Only the supported languages are listed. |

**Keys never go into git.** `.env`, `.env_training`, and `.env_recognition` are in `.gitignore`; only the `*.example` files are tracked, and they hold empty values. Keys pasted on the Settings page are stored in the hub's SQLite file inside the Docker volume `hub-data`, not in the repo, and the page shows only their last four characters. Before a commit, `git status` should never list `.env`, `.env_training`, `.env_recognition`, or a `*.db` file.

### Local models: hardware

Everything can run on one machine. Three parts use memory:

| Part | Runs on | Weight | Memory it needs |
| --- | --- | --- | --- |
| Speech recognition, English (`small.en`) | Host GPU (Metal, CUDA, or Vulkan), CPU fallback | 466 MB | about 1 GB |
| Speech recognition, Ukrainian, German (`large-v3-turbo`), Hebrew (ivrit.ai turbo) | Host GPU | 1.6 GB | about 2–3 GB |
| Speech recognition, Norsk (`nb-whisper-large`) | Host GPU | 3.1 GB | about 4 GB |
| Buddy, Ollama `qwen3:8b` (Q4_K_M) | Host GPU | about 5 GB | about 6 GB with context |
| Buddy, Ollama `qwen3:1.7b` | Host GPU or CPU | about 1.4 GB | about 2 GB |
| Voice, Piper | CPU, in Docker | 60–120 MB per voice | small |

Only one recognizer weight is loaded at a time; a language switch swaps it. The memory figures are approximate.

| Machine | Fully local setup |
| --- | --- |
| Apple Silicon, 16 GB or more | Default: `qwen3:8b` and every recognizer. 24 GB leaves room for Norsk's large weight beside the buddy. |
| NVIDIA, 12 GB VRAM or more | Default: `qwen3:8b` and every recognizer on the card. |
| NVIDIA, 8 GB VRAM | `qwen3:8b` fits alone. With Norsk's large recognizer beside it, layers spill to the CPU; use `qwen3:1.7b`, or a remote buddy. |
| NVIDIA, 4–6 GB VRAM | `qwen3:1.7b`, or a remote buddy. See [Slow replies](#slow-replies). |
| No GPU | Recognition works on the CPU but slowly. Use a remote buddy, and consider Google recognition. |

Settings for speed on a local model:

- `LLM_THINK=off` (the default). `qwen3:8b` then answers without a hidden reasoning pass.
- Check placement with `ollama ps`: `size_vram` should be almost all of `size`. Anything less means part of the model runs on the CPU.
- The first line after a start loads the model (tens of seconds). Ollama keeps it loaded for 30 minutes (`LLM_KEEP_ALIVE`).

### Remote models: speed

Grok and OpenAI are options for every part: the Buddy, Bob, Rob, and Wren. Set them on the **Models** tab, or in `.env`. Bob, Rob, and Wren work in the background or between rounds, so only the **Buddy** decides how long you wait after you speak.

Reasoning models think before they answer, and that thinking is most of the wait. In one measured session with `gpt-5-mini` at think `low`, a reply of about 30 words carried 150–950 hidden reasoning tokens and took 2.4–10 seconds. For the Buddy:

| Provider | Fastest setting |
| --- | --- |
| OpenAI | Think **`minimal`** (or `none` on models that accept it). Or a model that does not reason. |
| Grok | Think **`low`** (Grok cannot turn reasoning off). Or a non-reasoning model from the list the **Test** button fills, such as `grok-4.20-0309-non-reasoning`. |
| Local Ollama | Think **`off`**. |

Press **Test** beside a key on the Models tab to list the models that key can use.

English checks every Buddy reply and asks once more when the reply ignores your line or drifts into the text's story; that second call doubles the wait for that turn. The other languages keep the first reply in those cases.

To see the timing, watch the hub log:

```bash
docker compose logs -f cognitive-hub | grep -E "first-audio|HTTP 200"
```

`first-audio ms=…` is the time from your recording reaching the hub to the first sound of the reply. Each `openai …` or `grok …` line shows one model call with its time and token counts.

### Recommended setups

| Goal | Recognition | Buddy | Bob, Rob, Wren |
| --- | --- | --- | --- |
| Fully local, private | whisper on the host GPU | Ollama `qwen3:8b`, think `off` | Off (no key): no corrections, no Wren games |
| Best balance | whisper on the host GPU | OpenAI or Grok, think `minimal` / `low` | Same provider, think `low` |
| Fastest, any computer | Google recognition (Speech tab) | A non-reasoning remote model | Remote, think `low` |

### Change the model

`LLM_BACKEND` in `.env` chooses the Buddy's default provider. The Models tab overrides it per part without a restart.

| `LLM_BACKEND` | Who answers | What to set |
| --- | --- | --- |
| `local` | Ollama on this machine. Default `qwen3:8b`. | `LLM_BASE_URL` and `LLM_MODEL`. No API key. |
| `grok` | Grok at `https://api.x.ai/v1`. Default `grok-4.7`. | `XAI_API_KEY`. Optional `GROK_BASE_URL` and `GROK_MODEL`. |
| `openai` | OpenAI at `https://api.openai.com/v1`. Default `gpt-5-mini`. | `OPENAI_API_KEY`. Optional `OPENAI_BASE_URL` and `OPENAI_MODEL`. |

Bob, Rob, and Wren default to Grok from `config/bob.json`, `config/rob.json`, and `config/wren.json`. `BOB_BACKEND`, `ROB_BACKEND`, and `WREN_BACKEND` may be `xai` or `openai`. Each uses its own key variable (`BOB_API_KEY`, and so on) when set, then `XAI_API_KEY` or `OPENAI_API_KEY`.

**Another local model.** The name has to be one `ollama list` already shows.

```bash
ollama pull qwen3:1.7b
```

Then set `LLM_MODEL=qwen3:1.7b` in `.env` (or on the Models tab) and recreate the hub.

**Think levels.** `LLM_THINK` in `.env`, or the Think field on the Models tab.

| Backend | Levels | Default |
| --- | --- | --- |
| Local Ollama | `off`, `on`, `low`, `medium`, `high`, `max` | `off` |
| Grok | `low`, `medium`, `high`, `xhigh` | empty means `high`; the Models tab uses `low` |
| OpenAI | `none`, `minimal`, `low`, `medium`, `high`, `xhigh` (the model decides which it accepts) | empty means the model's default (`medium`); the Models tab uses `low` |

Grok cannot turn reasoning off, so `off` is refused for Grok in `.env`. A named local level works only when `ollama show <model>` lists it.

Training sets its own models in `.env_training` (`BACKEND_SIM_TALK`, `BACKEND_JUDGE_PROPOSER`: `local`, `grok`, or `openai`, with `SIM_TALK_THINK` and `JUDGE_PROPOSER_THINK`).

## Train the prompts

Copy `.env_training.example` to `.env_training`. That file chooses the two training models. Practice keeps using `.env`.

| Role | What it does | Variables |
| --- | --- | --- |
| `BACKEND_SIM_TALK` | Subject card and Buddy's lines in the simulated talks. | `SIM_TALK_BASE_URL`, `SIM_TALK_MODEL`, `SIM_TALK_API_KEY` |
| `BACKEND_JUDGE_PROPOSER` | Scores the talks and writes the next prompt. | `JUDGE_PROPOSER_BASE_URL`, `JUDGE_PROPOSER_MODEL`, `JUDGE_PROPOSER_API_KEY` |

Each backend is `local` or `grok`. `local` needs a base URL and a model name. `grok` needs an API key. An empty grok key uses `XAI_API_KEY` from the shell. The example file speaks with local `qwen3:8b` and judges with `grok-4.7`:

```bash
BACKEND_SIM_TALK=local
SIM_TALK_BASE_URL=http://127.0.0.1:11434/v1
SIM_TALK_MODEL=qwen3:8b
SIM_TALK_API_KEY=

BACKEND_JUDGE_PROPOSER=grok
JUDGE_PROPOSER_BASE_URL=https://api.x.ai/v1
JUDGE_PROPOSER_MODEL=grok-4.7
JUDGE_PROPOSER_API_KEY=
```

Swap either side to the other backend and set that side's model. `improve run` and `approve` read `.env_training` on the next command. The web page does not. `.env_training` stays untracked because it can hold a key.

The trainer replays three frozen English scripts, then asks for one change to either `config/prompts/prompt-of-subject-creation_en.md` or `config/prompts/ongoing_instruction_prompt_en.md`. A `local` role needs Ollama running with that model pulled.

From the repo root, with the package installed:

```bash
PYTHONPATH=cognitive-hub/src:shared/python .venv/bin/python -m logoskittens.sim improve run
```

Read the report it prints. It waits. Then either accept or refuse:

```bash
PYTHONPATH=cognitive-hub/src:shared/python .venv/bin/python -m logoskittens.sim improve approve
PYTHONPATH=cognitive-hub/src:shared/python .venv/bin/python -m logoskittens.sim improve reject
```

`approve` replays the proposal on `BACKEND_SIM_TALK`. When at least one score rose, none fell, and no fail-flag is set, it copies that prompt into `config/prompts/` and asks `BACKEND_JUDGE_PROPOSER` for the next proposal. `reject` records the refusal and does not write a new proposal.

Each round is a folder under `simulations/`. Commit `decision.md` and `scores.json`. Those hold the proposal, the full prompt text, the hypothesis, the scores, and the outcome. Git ignores traces, the copied config checkout, call logs, sqlite, audio, and model binaries inside those folders. See `simulations/README.md`.

## Languages

A language is a config pack. English files end in `_en`. Norwegian Bokmål is `nb`, with files under `config/languages`, `config/prompts`, `config/buddies/nb`, and `config/raw_materials/nb`. The Talk panel lists English, Norsk, Українська, Deutsch, and עברית. Choosing עברית mirrors the page right to left. A click reloads that pack and switches the recognizer. Editing those files does not need an image rebuild. The hub re-reads them on the next catalog or select. Lucas (man) and Ingrid (woman) both speak with `no_NO-talesyntese-medium`. Ukrainian (`uk`, Тарас and Танюша) and German (`de`, Jonas and Lena) are packs of the same shape. German speaks with Piper `de_DE-thorsten-medium` (Jonas, and Savelij as teacher) and `de_DE-kerstin-low` (Lena), and recognition uses `ggml-large-v3-turbo.bin` with `-l de`. Hebrew (`he`, נועם and מאיה) speaks with Piper `he_IL-saspeech-medium`, the only Hebrew Piper voice, so both buddies sound male; recognition uses ivrit.ai's Hebrew-tuned `whisper-large-v3-turbo` (a 1.6 GB download on the next `./scripts/host_whisper.sh`).

## Troubleshooting

### Slow replies

A typed line does not use the microphone. A long wait with no error in the Compose logs is the local model. Each buddy turn calls it once, and the page shows Buddy after that reply is finished. With `qwen3:8b` fully on the GPU, a short line is a few seconds. Tens of seconds means the model does not fit on the card, so most layers run on the CPU.

Check the card, then check that Ollama actually placed the model on it:

```bash
nvidia-smi
ollama ps
```

`nvidia-smi` prints the GPU and its total VRAM. In `ollama ps`, `size` is the loaded model and `size_vram` is the part resident on the GPU. Those two should be nearly the same. A large gap means the rest is on the CPU, and every token waits on that split. `journalctl -u ollama` prints `offloaded N/M layers to GPU`. N should equal M.

Minimum for the default `qwen3:8b` (Q4_K_M, about 5 GB of weights, about 5 GB of device memory with context and scratch): an NVIDIA GPU with **8 GB** of VRAM, and `size_vram` covering `size`. A 4 GB card is not appropriate for this model. On a GeForce GTX 1650 (4 GB) only 14 of 37 layers fit, generation stays near 6 tokens per second, and one typed line takes about 20 seconds per partner after the model is loaded. The first line also spends about 40 seconds loading it.

| Machine | What to run |
| --- | --- |
| NVIDIA, 8 GB VRAM or more | Default `qwen3:8b`. Require `size_vram` ≈ `size`. |
| NVIDIA, 4 GB VRAM | Do not use `qwen3:8b`. Follow [Change the model](#change-the-model) and set `LLM_MODEL=qwen3:1.7b`. |
| No NVIDIA GPU, or `nvidia-smi` missing | Below the minimum for `qwen3:8b`. Use a smaller model, or `LLM_BACKEND=grok`. |

After any model change, run `ollama ps` again. Accept the setup only when `size_vram` is almost all of `size`.

## MVP Task

Free speech with Buddy. The human holds the mic or types. The subject comes from a raw material, summarized once. The first material is a vacation in Norway. `buddy-two` is stored and inactive. The same `ElementSolution` is what a later hexapod adapter executes.

## Technology Highlights

- **STT / TTS:** whisper.cpp (`nb-whisper-large`, on the host GPU) + Silero VAD, Piper TTS (local, zero cost)
- **LLM:** one OpenAI-compatible `httpx` client — local models and Grok as MVP backends
- **Orchestration:** LangGraph (GroupSolution = conversation logic)
- **Persistence:** SQLite + SQLModel (embedded, lightweight, free)
- **Contracts:** Protocol Buffers
- **Frontend:** React + Vite + TypeScript
- **Robotics (later):** ROS 2 + Zenoh bridge

## Status

The free-speech loop runs in Docker Compose: audio engine, cognitive hub, and virtual stage. The talk is specified in `free_conv.md`.

See `logoskittens_architecture.md` for the primitives, the protobuf, and the robot transition.
