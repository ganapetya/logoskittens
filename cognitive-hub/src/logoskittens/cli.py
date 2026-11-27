"""Drive one hub turn without the browser.

    python -m logoskittens.cli --text "The fjords were quiet." --hub ws://localhost:8090/ws
    python -m logoskittens.cli --audio greeting.wav --hub ws://localhost:8090/ws
"""

import argparse
import asyncio
import base64
import json
import sys
import wave
from pathlib import Path

import websockets

from logoskittens.wire import PCM_CHANNELS, PCM_SAMPLE_RATE, PCM_SAMPLE_WIDTH, decode


def main() -> None:
    parser = argparse.ArgumentParser(description="Send one LogosKittens turn")
    parser.add_argument("--hub", default="ws://localhost:8090/ws")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text")
    group.add_argument("--audio", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("."))
    args = parser.parse_args()
    asyncio.run(_run(args.hub, args.text, args.audio, args.out_dir))


async def _run(hub: str, text: str | None, audio: Path | None, out_dir: Path) -> None:
    async with websockets.connect(hub) as socket:
        await socket.send(json.dumps({"type": "start"}))
        hello = json.loads(await socket.recv())
        print(f"session {hello.get('session_id')}")
        if text is not None:
            await socket.send(json.dumps({"type": "transcript", "text": text}))
        else:
            payload = audio.read_bytes()
            await socket.send(
                json.dumps(
                    {
                        "type": "audio",
                        "mime": "audio/wav",
                        "data": base64.b64encode(payload).decode("ascii"),
                    }
                )
            )
        out_dir.mkdir(parents=True, exist_ok=True)
        index = 0
        while True:
            reply = json.loads(await socket.recv())
            if reply.get("type") == "error":
                print(reply["message"], file=sys.stderr)
                sys.exit(1)
            if reply.get("type") == "heard":
                print(f"transcript: {reply.get('transcript')}")
                if reply.get("notice"):
                    print(reply["notice"])
            for encoded in reply.get("solutions") or []:
                solution = decode(base64.b64decode(encoded))
                print(f"{solution.actor_id} [{solution.emotion}] {solution.speech.text}")
                wav_path = out_dir / f"turn-{index}-{solution.actor_id}.wav"
                _write_wav(wav_path, solution.speech.precomputed_audio_pcm)
                print(f"  wrote {wav_path}")
                index += 1
            if reply.get("final"):
                break


def _write_wav(path: Path, pcm: bytes) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(PCM_CHANNELS)
        handle.setsampwidth(PCM_SAMPLE_WIDTH)
        handle.setframerate(PCM_SAMPLE_RATE)
        handle.writeframes(pcm)


if __name__ == "__main__":
    main()
