import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class JsonStore:
    path: Path

    def load(self) -> Any:
        if not self.path.exists():
            return None
        raw = self.path.read_text(encoding="utf-8").strip()
        if not raw:
            return None
        return json.loads(raw)

    def load_list(self) -> list[dict]:
        data = self.load()
        if data is None:
            return []
        if not isinstance(data, list):
            return []
        return [x for x in data if isinstance(x, dict)]

    def save(self, data: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

