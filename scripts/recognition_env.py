"""English recognizer weight from `.env_recognition`.

The launcher downloads that one ggml file. Norwegian stays a separate weight.
"""

import shlex
import sys
from pathlib import Path

FILE_NAME = ".env_recognition"
EXAMPLE_NAME = ".env_recognition.example"
DEFAULT_MODEL = "small.en"
DEFAULT_THREADS = 10
HF = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main"

_FULL = (
    "tiny.en",
    "base.en",
    "small.en",
    "medium.en",
    "tiny",
    "base",
    "small",
    "medium",
    "large-v1",
    "large-v2",
    "large-v3",
    "large-v3-turbo",
)
_QUANT = (
    "tiny-q5_1",
    "tiny-q8_0",
    "tiny.en-q5_1",
    "tiny.en-q8_0",
    "base-q5_1",
    "base-q8_0",
    "base.en-q5_1",
    "base.en-q8_0",
    "small-q5_1",
    "small-q8_0",
    "small.en-q5_1",
    "small.en-q8_0",
    "medium-q5_0",
    "medium-q8_0",
    "medium.en-q5_0",
    "medium.en-q8_0",
    "large-v2-q5_0",
    "large-v2-q8_0",
    "large-v3-q5_0",
    "large-v3-turbo-q5_0",
    "large-v3-turbo-q8_0",
)
MODELS = frozenset(_FULL + _QUANT)


class RecognitionConfig:
    def __init__(self, model: str, threads: int, source: str):
        self.model = model
        self.threads = threads
        self.source = source

    @property
    def filename(self) -> str:
        return f"ggml-{self.model}.bin"

    @property
    def url(self) -> str:
        return f"{HF}/{self.filename}"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_env(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            found[key] = value
    return found


def config_path(repo: Path) -> Path | None:
    local = repo / FILE_NAME
    example = repo / EXAMPLE_NAME
    if local.is_file():
        return local
    if example.is_file():
        return example
    return None


def load(repo: Path | None = None) -> RecognitionConfig:
    root = repo or repo_root()
    path = config_path(root)
    values: dict[str, str] = {}
    source = "(default)"
    if path is not None:
        values = parse_env(path.read_text(encoding="utf-8"))
        source = str(path)
    model = values.get("RECOGNITION_MODEL", "").strip() or DEFAULT_MODEL
    if model not in MODELS:
        names = ", ".join(_FULL)
        raise SystemExit(
            f"RECOGNITION_MODEL must be a whisper.cpp weight. Unknown: {model}\n"
            f"Full sizes: {names}\n"
            "Quantized names are in .env_recognition.example."
        )
    raw_threads = values.get("RECOGNITION_THREADS", "").strip()
    threads = DEFAULT_THREADS
    if raw_threads:
        try:
            threads = int(raw_threads)
        except ValueError as exc:
            raise SystemExit("RECOGNITION_THREADS must be a whole number") from exc
        if threads < 1 or threads > 32:
            raise SystemExit("RECOGNITION_THREADS must be from 1 to 32")
    return RecognitionConfig(model, threads, source)


def shell_lines(config: RecognitionConfig) -> str:
    pairs = {
        "recognition_model": config.model,
        "recognition_file": config.filename,
        "recognition_url": config.url,
        "recognition_threads": str(config.threads),
    }
    return "\n".join(f"{key}={shlex.quote(value)}" for key, value in pairs.items())


def powershell_lines(config: RecognitionConfig) -> str:
    pairs = {
        "RecognitionModel": config.model,
        "RecognitionFile": config.filename,
        "RecognitionUrl": config.url,
        "RecognitionThreads": str(config.threads),
    }
    return "\n".join(f"${key} = '{value}'" for key, value in pairs.items())


def main() -> None:
    config = load()
    print(f"recognition config: {config.source} model: {config.model}", file=sys.stderr)
    if "--powershell" in sys.argv:
        print(powershell_lines(config))
    else:
        print(shell_lines(config))


if __name__ == "__main__":
    main()
