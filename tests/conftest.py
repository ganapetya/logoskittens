import pytest


@pytest.fixture(autouse=True)
def _bob_stays_offline(monkeypatch):
    """A shell key must not make the suite call xAI. A BOB test turns this back on."""
    monkeypatch.setenv("BOB_ENABLED", "off")
    monkeypatch.setenv("WREN_ENABLED", "off")
    # A background prefetch would add a Wren call to a test's count. A prefetch test turns it on.
    monkeypatch.setenv("WREN_PREFETCH", "off")
    # Speech starts local in every test, whatever the developer's hub database says.
    from logoskittens.speech import settings as speech_settings

    speech_settings.reset()
    # Model choices start from the environment too.
    from logoskittens import models

    models.reset()
