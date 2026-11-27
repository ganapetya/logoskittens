#!/usr/bin/env python3
"""Print one line per extra recognition weight: `language weight_file url`.

English and Norsk keep their own launcher settings. Any other file in
config/languages that names `whisper.weight_file` and `whisper.url` is listed,
so the launcher can download it once and pass `--model language=path`.
"""

import json
import os
import sys
from pathlib import Path

OWN_SETTINGS = {"en", "nb"}


def rows(config_dir: Path) -> list[tuple[str, str, str]]:
    found = []
    for path in sorted((config_dir / "languages").glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        language = str(doc.get("id") or path.stem)
        whisper = doc.get("whisper") or {}
        weight = str(whisper.get("weight_file") or "").strip()
        url = str(whisper.get("url") or "").strip()
        if language in OWN_SETTINGS or not weight or not url:
            continue
        if any(char.isspace() for char in language + weight + url) or "/" in weight or "\\" in weight:
            continue
        found.append((language, weight, url))
    return found


def main() -> int:
    env = os.environ.get("LOGOSKITTENS_CONFIG", "").strip()
    root = Path(env) if env else Path(__file__).resolve().parents[1] / "config"
    for language, weight, url in rows(root):
        sys.stdout.write(f"{language} {weight} {url}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
