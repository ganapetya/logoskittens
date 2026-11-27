"""The host supervisor loads one Whisper weight, then replaces it."""

import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def _free_port() -> int:
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


def _get(port: int) -> dict:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=2) as response:
        return json.loads(response.read().decode())


def _post(port: int, language: str) -> dict:
    body = json.dumps({"language": language}).encode()
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/switch",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode())


def _wait_for_log(path: Path, fragment: str) -> str:
    deadline = time.time() + 3
    text = ""
    while time.time() < deadline:
        if path.exists():
            text = path.read_text()
            if fragment in text:
                return text
        time.sleep(0.05)
    raise AssertionError(text or "recognizer log was not written")


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def test_language_switch_replaces_the_process(tmp_path: Path):
    log = tmp_path / "whisper.log"
    fake = tmp_path / "whisper-server"
    script = "\n".join(
        [
            "#!/usr/bin/env python3",
            "import socket, sys, time",
            "argv = sys.argv",
            "port = int(argv[argv.index('--port') + 1])",
            "gate = socket.socket()",
            "gate.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)",
            "gate.bind(('127.0.0.1', port))",
            "gate.listen(1)",
            "line = str(__import__('os').getpid()) + ' ' + ' '.join(sys.argv)",
            f"handle = open({str(log)!r}, 'a', buffering=1)",
            "handle.write(line + '\\n')",
            "handle.flush()",
            "time.sleep(30)",
            "",
        ]
    )
    fake.write_text(script)
    fake.chmod(0o755)
    nb = tmp_path / "ggml-nb-whisper-medium.bin"
    en = tmp_path / "ggml-base.en.bin"
    vad = tmp_path / "vad.bin"
    nb.write_bytes(b"nb")
    en.write_bytes(b"en")
    vad.write_bytes(b"vad")
    config = tmp_path / "config" / "languages"
    config.mkdir(parents=True)
    (config / "en.json").write_text(
        json.dumps({"id": "en", "whisper": {"flag": "en", "model": "ggml-base.en", "weight_file": "ggml-base.en.bin"}}),
        encoding="utf-8",
    )
    (config / "nb.json").write_text(
        json.dumps(
            {
                "id": "nb",
                "whisper": {
                    "flag": "no",
                    "model": "nb-whisper-medium",
                    "weight_file": "ggml-nb-whisper-medium.bin",
                },
            }
        ),
        encoding="utf-8",
    )
    control = _free_port()
    listen = _free_port()
    env = dict(**os.environ)
    env["LOGOSKITTENS_CONFIG"] = str(tmp_path / "config")
    proc = subprocess.Popen(
        [
            sys.executable,
            "scripts/whisper_supervisor.py",
            "--server",
            str(fake),
            "--nb-model",
            str(nb),
            "--en-model",
            str(en),
            "--vad",
            str(vad),
            "--port",
            str(listen),
            "--control-port",
            str(control),
            "--threads",
            "2",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    first = 0
    try:
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                status = _get(control)
            except OSError:
                time.sleep(0.05)
                continue
            if status.get("pid"):
                break
            time.sleep(0.05)
        else:
            output = proc.stdout.read() if proc.stdout else ""
            raise AssertionError(output or "supervisor did not start")
        status = _get(control)
        assert status["language"] == "en"
        assert status["model"] == "ggml-base.en"
        first = int(status["pid"])
        _wait_for_log(log, "-l en")
        switched = _post(control, "nb")
        assert switched["restarted"] is True
        assert switched["model"] == "nb-whisper-medium"
        assert not _alive(first)
        status = _get(control)
        assert status["language"] == "nb"
        assert status["model"] == "nb-whisper-medium"
        second = int(status["pid"])
        assert second != first
        assert _alive(second)
        same = _post(control, "nb")
        assert same["restarted"] is False
        assert _get(control)["pid"] == second
        text = _wait_for_log(log, "-l en")
        assert str(nb) in text
        assert "-l no" in text
        assert str(en) in text
        assert "-l en" in text
        assert text.count("ggml") >= 1
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    if first:
        deadline = time.time() + 2
        while time.time() < deadline and _alive(first):
            time.sleep(0.05)
        assert not _alive(first)


def test_a_language_file_added_after_start_is_switchable(tmp_path: Path):
    log = tmp_path / "whisper.log"
    fake = tmp_path / "whisper-server"
    fake.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import socket, sys, time",
                "argv = sys.argv",
                "port = int(argv[argv.index('--port') + 1])",
                "gate = socket.socket()",
                "gate.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)",
                "gate.bind(('127.0.0.1', port))",
                "gate.listen(1)",
                "line = ' '.join(sys.argv)",
                f"handle = open({str(log)!r}, 'a', buffering=1)",
                "handle.write(line + '\\n')",
                "handle.flush()",
                "time.sleep(30)",
                "",
            ]
        )
    )
    fake.chmod(0o755)
    nb = tmp_path / "ggml-nb-whisper-medium.bin"
    en = tmp_path / "ggml-base.en.bin"
    vad = tmp_path / "vad.bin"
    nb.write_bytes(b"nb")
    en.write_bytes(b"en")
    vad.write_bytes(b"vad")
    config = tmp_path / "config" / "languages"
    config.mkdir(parents=True)
    (config / "en.json").write_text(
        json.dumps({"id": "en", "whisper": {"flag": "en", "model": "ggml-base.en", "weight_file": "ggml-base.en.bin"}}),
        encoding="utf-8",
    )
    control = _free_port()
    listen = _free_port()
    env = dict(**os.environ)
    env["LOGOSKITTENS_CONFIG"] = str(tmp_path / "config")
    proc = subprocess.Popen(
        [
            sys.executable,
            "scripts/whisper_supervisor.py",
            "--server",
            str(fake),
            "--nb-model",
            str(nb),
            "--en-model",
            str(en),
            "--vad",
            str(vad),
            "--port",
            str(listen),
            "--control-port",
            str(control),
            "--threads",
            "2",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    try:
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                status = _get(control)
            except OSError:
                time.sleep(0.05)
                continue
            if status.get("language") == "en" and status.get("pid"):
                break
            time.sleep(0.05)
        else:
            output = proc.stdout.read() if proc.stdout else ""
            raise AssertionError(output or "supervisor did not start")
        try:
            missing = _post(control, "nb")
        except urllib.error.HTTPError as exc:
            missing = json.loads(exc.read().decode())
        assert missing["ok"] is False
        (config / "nb.json").write_text(
            json.dumps(
                {
                    "id": "nb",
                    "whisper": {
                        "flag": "no",
                        "model": "nb-whisper-medium",
                        "weight_file": "ggml-nb-whisper-medium.bin",
                    },
                }
            ),
            encoding="utf-8",
        )
        switched = _post(control, "nb")
        assert switched["ok"] is True
        assert switched["restarted"] is True
        assert switched["model"] == "nb-whisper-medium"
        text = _wait_for_log(log, "-l no")
        assert "-l no" in text
        assert str(nb) in text
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
