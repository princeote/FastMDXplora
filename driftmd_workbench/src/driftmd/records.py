from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class StepRecord:
    name: str
    status: str
    started_at: str
    finished_at: str
    output_dir: str
    artifacts: list[str] = field(default_factory=list)
    message: str = ""
    error_type: str | None = None


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def append_record(root: Path, record: StepRecord) -> None:
    manifest_path = root / "run_manifest.json"
    manifest = read_json(manifest_path, {"tool": "DriftMD Workbench", "phases": []})
    manifest.setdefault("phases", []).append(asdict(record))
    write_json(manifest_path, manifest)


def phase_names(root: Path) -> set[str]:
    manifest = read_json(root / "run_manifest.json", {})
    phases = manifest.get("phases", [])
    return {
        str(item.get("name"))
        for item in phases
        if isinstance(item, dict) and item.get("status") == "ok"
    }
