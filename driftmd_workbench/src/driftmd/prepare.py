from __future__ import annotations

import shutil
from pathlib import Path

from driftmd.records import StepRecord, append_record, utc_now, write_json


def prepare_structure(structure: Path, root: Path) -> StepRecord:
    started = utc_now()
    out = root / "prepare"
    out.mkdir(parents=True, exist_ok=True)
    copied = out / "input_structure.pdb"
    cleaned = out / "prepared_structure.pdb"
    shutil.copyfile(structure, copied)
    shutil.copyfile(structure, cleaned)
    write_json(
        out / "prepare_manifest.json",
        {
            "input": str(structure),
            "prepared_structure": str(cleaned),
            "note": "First version records and stages the structure without chemistry repair.",
        },
    )
    record = StepRecord(
        name="prepare",
        status="ok",
        started_at=started,
        finished_at=utc_now(),
        output_dir=str(out),
        artifacts=["input_structure.pdb", "prepared_structure.pdb", "prepare_manifest.json"],
        message="Structure staged for downstream phases.",
    )
    append_record(root, record)
    return record
