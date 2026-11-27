"""Raw material: sentences the talk is about.

Files live under ``config/raw_materials``. A downloaded LogosCat workspace
session, and a material the user wrote (``own-…``), are rows in the hub
database and use the same load path.
"""

import uuid
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field

from logoskittens.content import config_root

DEFAULT_MATERIAL_ID = "norway_vacation_tunnels_fjords"
OWN_PREFIX = "own-"
TITLE_MAX = 120
TEXT_MAX = 20_000
SENTENCES_MIN = 2


class RawMaterial(BaseModel):
    id: str = Field(min_length=1)
    language: str = Field(min_length=1)
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    origin: str = "file"
    logoscat_user_id: int = 0


class RawMaterialSource(Protocol):
    def load(self, language: str, material_id: str) -> RawMaterial: ...


class FileRawMaterialSource:
    """Read ``config/raw_materials/{language}/{id}.txt``."""

    def __init__(self, root: Path | None = None):
        self.root = root

    def _folder(self, language: str) -> Path:
        base = self.root or config_root()
        return base / "raw_materials" / language

    def list(self, language: str) -> list[RawMaterial]:
        folder = self._folder(language)
        if not folder.is_dir():
            return []
        items = []
        for path in sorted(folder.glob("*.txt")):
            items.append(self._read(language, path))
        return items

    def load(self, language: str, material_id: str) -> RawMaterial:
        path = self._folder(language) / f"{material_id}.txt"
        if not path.is_file():
            raise FileNotFoundError(f"no raw material {language}/{material_id}")
        return self._read(language, path)

    def _read(self, language: str, path: Path) -> RawMaterial:
        raw = path.read_text(encoding="utf-8").strip()
        title = path.stem.replace("_", " ")
        lines = raw.splitlines()
        if lines and lines[0].lower().startswith("title:"):
            title = lines[0].split(":", 1)[1].strip() or title
            raw = "\n".join(lines[1:]).strip()
        if not raw:
            raise ValueError(f"{path.name} has no sentences")
        return RawMaterial(id=path.stem, language=language, title=title, text=raw, origin="file")


def menu_item(item: RawMaterial) -> dict:
    """What the raw-material list shows. The sentences stay on the hub."""
    return {
        "id": item.id,
        "language": item.language,
        "title": item.title,
        "origin": item.origin,
        "logoscat_user_id": item.logoscat_user_id,
    }


class MaterialLibrary:
    """Files, plus workspace sessions already downloaded for this hub."""

    def __init__(self, store, files: FileRawMaterialSource | None = None):
        self.store = store
        self.files = files or FileRawMaterialSource()

    def list(self, language: str) -> list[RawMaterial]:
        found = self.files.list(language)
        for row in self.store.list_logoscat_materials(language):
            found.append(_from_row(row))
        for row in self.store.list_own_materials(language):
            found.append(_from_own(row))
        return found

    def load(self, language: str, material_id: str) -> RawMaterial:
        if str(material_id).startswith("logoscat-"):
            row = self.store.get_logoscat_material(material_id)
            if row is None:
                raise ValueError("That LogosCat session is not on this hub.")
            if row.language != language:
                raise ValueError("That session is in another language.")
            return _from_row(row)
        if str(material_id).startswith(OWN_PREFIX):
            row = self.store.get_own_material(material_id)
            if row is None:
                raise ValueError("That material is not on this hub.")
            if row.language != language:
                raise ValueError("That material is in another language.")
            return _from_own(row)
        return self.files.load(language, material_id)

    def add_own(self, language: str, title: str, text: str) -> RawMaterial:
        title, text = validate_own(language, title, text)
        material_id = f"{OWN_PREFIX}{uuid.uuid4().hex[:12]}"
        self.store.save_own_material(material_id, language=language, title=title, text=text)
        return self.load(language, material_id)

    def edit_own(self, material_id: str, title: str, text: str) -> RawMaterial:
        row = self.store.get_own_material(material_id) if str(material_id).startswith(OWN_PREFIX) else None
        if row is None:
            raise LookupError("That material is not on this hub.")
        title, text = validate_own(row.language, title, text)
        self.store.save_own_material(material_id, language=row.language, title=title, text=text)
        return self.load(row.language, material_id)

    def delete_own(self, material_id: str) -> bool:
        if not str(material_id).startswith(OWN_PREFIX):
            raise ValueError("Only a material you added can be deleted here.")
        return self.store.delete_own_material(material_id)


def validate_own(language: str, title: str, text: str) -> tuple[str, str]:
    """The stored title and text, or ValueError with a sentence the page can show."""
    from logoskittens.content import languages
    from logoskittens.talk import split_sentences

    if language not in languages():
        raise ValueError("LogosKittens cannot talk in that language yet.")
    lines = [" ".join(line.split()) for line in str(text or "").splitlines()]
    if lines and lines[0].lower().startswith("title:"):
        lines = lines[1:]
    body = "\n".join(line for line in lines if line).strip()
    name = " ".join(str(title or "").split())
    if not name:
        raise ValueError("Give the material a title.")
    if len(name) > TITLE_MAX:
        raise ValueError(f"The title is longer than {TITLE_MAX} characters.")
    if len(body) > TEXT_MAX:
        raise ValueError(f"The text is longer than {TEXT_MAX} characters.")
    if len([part for part in split_sentences(body) if part.strip()]) < SENTENCES_MIN:
        raise ValueError("Write at least two sentences.")
    return name, body


def _from_row(row) -> RawMaterial:
    return RawMaterial(
        id=row.id,
        language=row.language,
        title=row.title,
        text=row.text,
        origin="logoscat",
        logoscat_user_id=row.logoscat_user_id,
    )


def _from_own(row) -> RawMaterial:
    return RawMaterial(id=row.id, language=row.language, title=row.title, text=row.text, origin="own")


def active_source() -> FileRawMaterialSource:
    """The file reader. A downloaded session is loaded by ``MaterialLibrary``."""
    return FileRawMaterialSource()