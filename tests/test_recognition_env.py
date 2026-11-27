"""The recognizer weight comes from .env_recognition."""

import pytest

from scripts.recognition_env import (
    DEFAULT_MODEL,
    EXAMPLE_NAME,
    load,
    parse_env,
    powershell_lines,
    shell_lines,
)


def test_the_example_selects_small_en():
    config = load()
    assert config.model == "small.en"
    assert config.model == DEFAULT_MODEL
    assert config.filename == "ggml-small.en.bin"
    assert config.filename in config.url
    assert config.threads == 10
    assert config.source.endswith(EXAMPLE_NAME) or config.source.endswith(".env_recognition")


def test_a_local_file_overrides_the_example(tmp_path):
    (tmp_path / ".env_recognition.example").write_text(
        "RECOGNITION_MODEL=base.en\n",
        encoding="utf-8",
    )
    (tmp_path / ".env_recognition").write_text(
        "# keep the comments\nRECOGNITION_MODEL=\"medium.en\"\nRECOGNITION_THREADS=4\n",
        encoding="utf-8",
    )
    config = load(tmp_path)
    assert config.model == "medium.en"
    assert config.threads == 4
    assert config.source.endswith(".env_recognition")
    assert "medium.en" in shell_lines(config)
    assert "$RecognitionModel = 'medium.en'" in powershell_lines(config)


def test_comments_and_a_missing_file_keep_the_default(tmp_path):
    assert parse_env("# RECOGNITION_MODEL=large-v3\n\nRECOGNITION_THREADS=\n") == {
        "RECOGNITION_THREADS": ""
    }
    (tmp_path / ".env_recognition.example").write_text("# none\n", encoding="utf-8")
    config = load(tmp_path)
    assert config.model == "small.en"


def test_an_unknown_model_is_refused(tmp_path):
    (tmp_path / ".env_recognition").write_text("RECOGNITION_MODEL=nope\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="Unknown: nope"):
        load(tmp_path)
