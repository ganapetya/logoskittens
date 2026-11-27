"""Ask the host supervisor to load one Whisper weight.

The hub cannot restart the host process itself. If port 8083 is down, the
language selection is still saved and the next Speak uses whatever weight
is already loaded.
"""

import os

import httpx


def switch_recognizer(language_id: str, timeout: float = 60.0) -> dict:
    from logoskittens.content import has_recognizer

    if not has_recognizer(language_id):
        return {"ok": False, "restarted": False, "detail": "saved without a recognizer restart"}
    base = os.environ.get("WHISPER_CONTROL_URL", "http://host.docker.internal:8083").rstrip("/")
    try:
        response = httpx.post(
            f"{base}/switch",
            json={"language": language_id},
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        return {"ok": False, "restarted": False, "detail": f"control port is down: {exc}"}
    if response.status_code >= 400:
        return {"ok": False, "restarted": False, "detail": response.text[:200]}
    try:
        body = response.json()
    except ValueError:
        body = {}
    body["ok"] = True
    return body
