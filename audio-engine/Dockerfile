FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        wget ca-certificates ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Speech recognition runs on the host GPU. This image is Piper only.
# The lesson voice is talesyntese. nvcc is present and is not the lesson default. English has two voice files.
RUN mkdir -p /models/piper \
    && wget -q -O /models/piper/no_NO-talesyntese-medium.onnx \
        https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/no/no_NO/talesyntese/medium/no_NO-talesyntese-medium.onnx \
    && wget -q -O /models/piper/no_NO-talesyntese-medium.onnx.json \
        https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/no/no_NO/talesyntese/medium/no_NO-talesyntese-medium.onnx.json \
    && wget -q -O /models/piper/en_US-ryan-medium.onnx \
        https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/medium/en_US-ryan-medium.onnx \
    && wget -q -O /models/piper/en_US-ryan-medium.onnx.json \
        https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/medium/en_US-ryan-medium.onnx.json \
    && wget -q -O /models/piper/en_US-lessac-medium.onnx \
        https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx \
    && wget -q -O /models/piper/en_US-lessac-medium.onnx.json \
        https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
# nvcc was published after the v1.0.0 voice tag. K is female, M is male.
RUN wget -q -O /models/piper/no_NO-nvcc-medium.onnx \
        https://huggingface.co/rhasspy/piper-voices/resolve/c10ece1aade47bb51c153c893d14e5bf8e5b7117/no/no_NO/nvcc/medium/no_NO-nvcc-medium.onnx \
    && wget -q -O /models/piper/no_NO-nvcc-medium.onnx.json \
        https://huggingface.co/rhasspy/piper-voices/resolve/c10ece1aade47bb51c153c893d14e5bf8e5b7117/no/no_NO/nvcc/medium/no_NO-nvcc-medium.onnx.json

# Ukrainian: one multi-speaker file. Speakers are lada, mykyta (male), and tetiana (female).
RUN wget -q -O /models/piper/uk_UA-ukrainian_tts-medium.onnx \
        https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/uk/uk_UA/ukrainian_tts/medium/uk_UA-ukrainian_tts-medium.onnx \
    && wget -q -O /models/piper/uk_UA-ukrainian_tts-medium.onnx.json \
        https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/uk/uk_UA/ukrainian_tts/medium/uk_UA-ukrainian_tts-medium.onnx.json

# German: Thorsten (male, medium) and Kerstin (female, low).
RUN wget -q -O /models/piper/de_DE-thorsten-medium.onnx \
        https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx \
    && wget -q -O /models/piper/de_DE-thorsten-medium.onnx.json \
        https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx.json \
    && wget -q -O /models/piper/de_DE-kerstin-low.onnx \
        https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/de/de_DE/kerstin/low/de_DE-kerstin-low.onnx \
    && wget -q -O /models/piper/de_DE-kerstin-low.onnx.json \
        https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/de/de_DE/kerstin/low/de_DE-kerstin-low.onnx.json

# Hebrew: one male voice (saspeech). It needs Piper 1.6 or newer for its Hebrew phonemizer.
# Published after v1.0.0, so it is pinned to a commit.
RUN wget -q -O /models/piper/he_IL-saspeech-medium.onnx \
        https://huggingface.co/rhasspy/piper-voices/resolve/5ec43b186ef915a195d3ddbcfd9916e76c503c3f/he/he_IL/saspeech/medium/he_IL-saspeech-medium.onnx \
    && wget -q -O /models/piper/he_IL-saspeech-medium.onnx.json \
        https://huggingface.co/rhasspy/piper-voices/resolve/5ec43b186ef915a195d3ddbcfd9916e76c503c3f/he/he_IL/saspeech/medium/he_IL-saspeech-medium.onnx.json

WORKDIR /app
COPY audio-engine/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY audio-engine/server.py /app/server.py

EXPOSE 8081
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8081"]
