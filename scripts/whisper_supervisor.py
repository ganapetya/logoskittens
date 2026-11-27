#!/usr/bin/env python3
"""Keep one whisper-server process. A language switch stops it and starts the other weight.

Norwegian and English weights may both sit on disk. Only one is loaded.
The hub reaches this process at WHISPER_CONTROL_URL (default port 8083).
"""

import argparse
import json
import os
import signal
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_FALLBACK = {
    "nb": {"flag": "no", "model": "nb-whisper-large", "weight_file": "ggml-nb-whisper-large.bin"},
    "en": {"flag": "en", "model": "ggml-base.en", "weight_file": "ggml-base.en.bin"},
}


def load_languages(config_dir: Path | None = None) -> dict:
    """Read whisper flag and weight name from config/languages. Python stays the switch."""
    root = config_dir
    if root is None:
        env = os.environ.get("LOGOSKITTENS_CONFIG", "").strip()
        root = Path(env) if env else Path(__file__).resolve().parents[1] / "config"
    folder = root / "languages"
    found: dict[str, dict] = {}
    if folder.is_dir():
        for path in sorted(folder.glob("*.json")):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            whisper = doc.get("whisper") or {}
            language_id = str(doc.get("id") or path.stem)
            flag = str(whisper.get("flag") or "")
            model = str(whisper.get("model") or doc.get("recognizer_model") or "")
            if not flag or not model:
                continue
            found[language_id] = {
                "flag": flag,
                "model": model,
                "weight_file": str(whisper.get("weight_file") or ""),
            }
    return found or dict(_FALLBACK)


LANG = load_languages()


class Supervisor:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.lock = threading.Lock()
        self.proc: subprocess.Popen | None = None
        self.language = ""
        start = "en" if "en" in LANG else next(iter(LANG))
        self.switch(start)

    def _model_path(self, language: str) -> str:
        override = getattr(self.args, "model_paths", {}).get(language)
        if override:
            return override
        if language == "en":
            return self.args.en_model
        if language == "nb":
            return self.args.nb_model
        filename = LANG.get(language, {}).get("weight_file") or ""
        if filename:
            return str(Path(self.args.nb_model).parent / filename)
        return self.args.nb_model

    def _model_label(self, language: str) -> str:
        named = getattr(self.args, "en_name", "") or ""
        if language == "en" and named:
            return named
        return LANG.get(language, {}).get("model", "")

    def stop(self) -> None:
        proc = self.proc
        self.proc = None
        if proc is None or proc.poll() is not None:
            return
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except OSError:
            proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                proc.kill()
            proc.wait(timeout=5)

    def switch(self, language: str) -> dict:
        global LANG
        with self.lock:
            LANG = load_languages()
            if language not in LANG:
                return {"ok": False, "error": "unknown language"}
            if (
                language == self.language
                and self.proc is not None
                and self.proc.poll() is None
            ):
                return {
                    "ok": True,
                    "language": language,
                    "restarted": False,
                    "model": self._model_label(language),
                }
            self.stop()
            model = self._model_path(language)
            cmd = [
                self.args.server,
                "-m",
                model,
                "-l",
                LANG[language]["flag"],
                "-nt",
                "-t",
                str(self.args.threads),
                "--host",
                "0.0.0.0",
                "--port",
                str(self.args.port),
                "--vad",
                "--vad-min-speech-duration-ms",
                "100",
                "--vad-min-silence-duration-ms",
                "400",
                "--vad-speech-pad-ms",
                "300",
                "-vm",
                self.args.vad,
            ]
            proc = subprocess.Popen(cmd, start_new_session=True)
            self.proc = proc
            if not self._wait_until_listening(proc):
                self.stop()
                return {
                    "ok": False,
                    "language": language,
                    "restarted": False,
                    "error": "recognizer did not start",
                    "model": self._model_label(language),
                }
            self.language = language
            label = self._model_label(language)
            print(f"whisper language: {language} model: {label}", flush=True)
            return {
                "ok": True,
                "language": language,
                "restarted": True,
                "model": label,
                "pid": proc.pid,
            }

    def _wait_until_listening(self, proc: subprocess.Popen, timeout: float = 30.0) -> bool:
        """The new weight is the one on the port. The previous process is already gone."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if proc.poll() is not None:
                return False
            try:
                with socket.create_connection(("127.0.0.1", self.args.port), 0.3):
                    return True
            except OSError:
                time.sleep(0.2)
        return False

    def status(self) -> dict:
        with self.lock:
            pid = self.proc.pid if self.proc is not None and self.proc.poll() is None else None
            return {
                "language": self.language,
                "model": self._model_label(self.language) if self.language else "",
                "pid": pid,
            }


def serve(supervisor: Supervisor, port: int) -> None:
    owner = supervisor

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.split("?", 1)[0] != "/status":
                self.send_error(404)
                return
            body = json.dumps(owner.status()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path.split("?", 1)[0] != "/switch":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
                language = str(payload.get("language", ""))
            except (json.JSONDecodeError, TypeError):
                self.send_error(400)
                return
            result = owner.switch(language)
            status = 200 if result.get("ok") else 400
            body = json.dumps(result).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)

    def _stop(_signum, _frame):
        owner.stop()
        os._exit(0)

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    print(f"whisper control: {port}", flush=True)
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", required=True)
    parser.add_argument("--nb-model", required=True)
    parser.add_argument("--en-model", required=True)
    parser.add_argument("--en-name", default="")
    parser.add_argument(
        "--model",
        action="append",
        default=[],
        help="language=path for a weight that is not the Norwegian or English file",
    )
    parser.add_argument("--vad", required=True)
    parser.add_argument("--port", type=int, default=8082)
    parser.add_argument("--control-port", type=int, default=8083)
    parser.add_argument("--threads", type=int, default=10)
    args = parser.parse_args()
    paths: dict[str, str] = {}
    for item in args.model:
        language, sep, path = str(item).partition("=")
        if sep and language and path:
            paths[language] = path
    args.model_paths = paths
    supervisor = Supervisor(args)
    try:
        serve(supervisor, args.control_port)
    finally:
        supervisor.stop()


if __name__ == "__main__":
    main()
