"""Materials the user writes: per language, in the hub's SQLite file, used by the talk and the games."""

import pytest
from fastapi.testclient import TestClient

from fakes import FakeAudio, fake_complete

from logoskittens.api import create_app
from logoskittens.materials import TEXT_MAX
from logoskittens.persistence import Store
from logoskittens.session import SessionService

UK_TEXT = (
    "Учора ми гуляли старим містом. Вузькі вулиці вели до площі з фонтаном. "
    "Там ми пили каву й слухали вуличного музиканта. Увечері небо стало рожевим."
)
EN_TEXT = "We walked to the harbour at dawn. The boats were still asleep. A gull stood on every post."


def _service(tmp_path) -> SessionService:
    return SessionService(Store(tmp_path / "own.db"), FakeAudio(), fake_complete)  # type: ignore[arg-type]


def test_each_language_lists_only_its_own_materials_and_loads_them(tmp_path):
    library = _service(tmp_path).materials
    uk = library.add_own("uk", "  Прогулянка   містом ", UK_TEXT)
    en = library.add_own("en", "Harbour", EN_TEXT)
    library.add_own("uk", "Ще одна", "Перше речення. Друге речення.")
    assert uk.id.startswith("own-") and uk.origin == "own"
    assert uk.title == "Прогулянка містом"
    uk_ids = [item.id for item in library.list("uk") if item.origin == "own"]
    en_ids = [item.id for item in library.list("en") if item.origin == "own"]
    assert uk.id in uk_ids and en.id not in uk_ids
    assert en_ids == [en.id]
    assert len(uk_ids) == 2
    assert library.load("uk", uk.id).text == UK_TEXT
    with pytest.raises(ValueError):
        library.load("en", uk.id)


@pytest.mark.parametrize(
    ("language", "title", "text"),
    [
        ("uk", "", UK_TEXT),
        ("uk", "Назва", "Лише одне речення"),
        ("xx", "Title", EN_TEXT),
        ("en", "T" * 121, EN_TEXT),
        ("en", "Long", "A line. " * (TEXT_MAX // 8 + 1)),
    ],
)
def test_a_bad_material_is_refused(tmp_path, language, title, text):
    with pytest.raises(ValueError):
        _service(tmp_path).materials.add_own(language, title, text)


def test_a_title_line_in_the_text_is_dropped(tmp_path):
    item = _service(tmp_path).materials.add_own("en", "Harbour", "Title: Ignored\n" + EN_TEXT)
    assert item.text == EN_TEXT


def test_edit_and_delete_touch_only_own_materials(tmp_path):
    library = _service(tmp_path).materials
    item = library.add_own("uk", "Прогулянка", UK_TEXT)
    edited = library.edit_own(item.id, "Вечір", "Небо стало рожевим. Ми пішли додому.")
    assert edited.title == "Вечір"
    assert edited.language == "uk"
    assert library.load("uk", item.id).text == "Небо стало рожевим. Ми пішли додому."
    with pytest.raises(LookupError):
        library.edit_own("norway_vacation_tunnels_fjords", "X", EN_TEXT)
    with pytest.raises(ValueError):
        library.delete_own("logoscat-7")
    assert library.delete_own(item.id) is True
    assert library.delete_own(item.id) is False
    assert all(entry.id != item.id for entry in library.list("uk"))


def test_a_talk_and_a_local_game_run_on_an_own_material(tmp_path):
    from logoskittens.games.host import run_game_prepare
    from logoskittens.personalities import get_personality

    service = _service(tmp_path)
    item = service.materials.add_own("uk", "Прогулянка", UK_TEXT)
    session_id = service.select("user-local", "uk", item.id, "taras")
    described = service.describe(session_id)
    assert described["material_id"] == item.id
    assert any(entry["id"] == item.id and entry["title"] == "Прогулянка" for entry in described["materials"])
    prepared = run_game_prepare(
        service,
        game_id="word_order",
        material=item,
        language_id="uk",
        person=get_personality("uk", "taras"),
    )
    assert prepared.deck.targets
    assert all(target.phrase in UK_TEXT for target in prepared.deck.targets)


def test_the_routes_add_edit_and_delete(tmp_path):
    service = _service(tmp_path)
    client = TestClient(create_app(service))
    added = client.post("/materials", json={"language_id": "uk", "title": "Прогулянка", "text": UK_TEXT})
    assert added.status_code == 200
    material_id = added.json()["material_id"]
    listed = client.get("/catalog", params={"language_id": "uk"}).json()["materials"]
    assert any(entry["id"] == material_id and entry["origin"] == "own" for entry in listed)
    assert client.get(f"/materials/{material_id}", params={"language_id": "uk"}).json()["text"] == UK_TEXT
    bad = client.post("/materials", json={"language_id": "uk", "title": "Назва", "text": "Одне речення"})
    assert bad.status_code == 400 and bad.json()["error"]
    edited = client.put(f"/materials/{material_id}", json={"title": "Вечір", "text": UK_TEXT})
    assert edited.json()["title"] == "Вечір"
    assert client.put("/materials/own-missing", json={"title": "X", "text": EN_TEXT}).status_code == 404
    assert client.delete("/materials/norway_vacation_tunnels_fjords").status_code == 400
    assert client.delete(f"/materials/{material_id}").status_code == 200
    assert client.delete(f"/materials/{material_id}").status_code == 404
