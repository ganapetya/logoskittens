FROM python:3.11-slim-bookworm

WORKDIR /app
COPY bot-link /app/bot-link
COPY cognitive-hub/pyproject.toml /app/cognitive-hub/pyproject.toml
COPY cognitive-hub/MANIFEST.in /app/cognitive-hub/MANIFEST.in
COPY cognitive-hub/src /app/cognitive-hub/src
COPY shared/python /app/shared/python
COPY config /app/config
RUN pip install --no-cache-dir /app/bot-link /app/cognitive-hub
ENV PYTHONPATH=/app/shared/python
ENV SQLITE_PATH=/data/logoskittens.db
ENV LOGOSKITTENS_CONFIG=/app/config
EXPOSE 8080
CMD ["uvicorn", "logoskittens.api:app", "--host", "0.0.0.0", "--port", "8080"]
