"""Transcript history persisted to %APPDATA%\\SociusDictado\\history.json."""
from __future__ import annotations
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

import paths


@dataclass
class Item:
    id: str
    date: str          # ISO 8601
    duration: float    # seconds
    model: str
    text: str
    ai_title: Optional[str] = None
    versions: Optional[list] = None   # edit history: [{"id","date","text"}]; None for old items

    @property
    def words(self) -> int:
        return len(self.text.split())

    @property
    def title(self) -> str:
        if self.ai_title and self.ai_title.strip():
            return self.ai_title.strip()
        return self.fallback_title

    @property
    def fallback_title(self) -> str:
        t = self.text.strip()
        if not t:
            return "(vacío)"
        clause = t.splitlines()[0]
        for i, ch in enumerate(clause):
            if ch in ".!?" and i >= 12:
                clause = clause[:i]
                break
        if len(clause) <= 46:
            return clause[:1].upper() + clause[1:]
        cut = clause[:46]
        if " " in cut:
            cut = cut[:cut.rfind(" ")]
        return (cut[:1].upper() + cut[1:]) + "…"

    def date_display(self) -> str:
        try:
            dt = datetime.fromisoformat(self.date)
            return dt.strftime("%m/%d/%y, %I:%M %p")
        except Exception:
            return self.date

    def duration_display(self) -> str:
        s = int(round(self.duration))
        return f"{s // 60}m {s % 60}s" if s >= 60 else f"{s}s"


class Store:
    def __init__(self) -> None:
        self.items: list[Item] = []
        self._load()

    def _load(self) -> None:
        try:
            with open(paths.history_file(), "r", encoding="utf-8") as f:
                data = json.load(f)
            self.items = [Item(**d) for d in data]
        except Exception:
            self.items = []

    def _save(self) -> None:
        try:
            with open(paths.history_file(), "w", encoding="utf-8") as f:
                json.dump([asdict(i) for i in self.items], f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def add(self, text: str, duration: float, model: str) -> str:
        now = datetime.now().isoformat()
        item = Item(id=str(uuid.uuid4()), date=now,
                    duration=duration, model=model, text=text, ai_title=None,
                    versions=[{"id": str(uuid.uuid4()), "date": now, "text": text}])
        self.items.insert(0, item)
        self._save()
        return item.id

    def set_title(self, item_id: str, title: str) -> None:
        for it in self.items:
            if it.id == item_id:
                it.ai_title = title
                self._save()
                return

    # ---- editing + version history ----
    def versions_of(self, item_id: str) -> list:
        for it in self.items:
            if it.id == item_id:
                return it.versions if it.versions else [{"id": it.id, "date": it.date, "text": it.text}]
        return []

    def update_text(self, item_id: str, new_text: str) -> None:
        """Live edit: set current text, no new version."""
        for it in self.items:
            if it.id == item_id and it.text != new_text:
                it.text = new_text
                self._save()
                return

    def snapshot_version(self, item_id: str) -> None:
        """Record the current text as a new version if it changed."""
        for it in self.items:
            if it.id == item_id:
                vs = it.versions if it.versions else [{"id": it.id, "date": it.date, "text": it.text}]
                if not vs or vs[-1]["text"] != it.text:
                    vs = list(vs) + [{"id": str(uuid.uuid4()), "date": datetime.now().isoformat(), "text": it.text}]
                    it.versions = vs
                    self._save()
                elif it.versions is None:
                    it.versions = vs
                    self._save()
                return

    def restore(self, item_id: str, version: dict) -> None:
        for it in self.items:
            if it.id == item_id:
                vs = it.versions if it.versions else [{"id": it.id, "date": it.date, "text": it.text}]
                it.text = version["text"]
                if not vs or vs[-1]["text"] != version["text"]:
                    vs = list(vs) + [{"id": str(uuid.uuid4()), "date": datetime.now().isoformat(), "text": version["text"]}]
                it.versions = vs
                self._save()
                return

    def delete(self, item_id: str) -> None:
        self.items = [i for i in self.items if i.id != item_id]
        self._save()

    def delete_many(self, ids: set[str]) -> None:
        self.items = [i for i in self.items if i.id not in ids]
        self._save()

    def clear(self) -> None:
        self.items = []
        self._save()
