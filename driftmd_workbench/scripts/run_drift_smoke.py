from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from driftmd.prepare import prepare_structure
from driftmd.report import build_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run small DriftMD smoke workflows.")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("structures", nargs="+")
    return parser


def _safe_id(path: Path) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in path.stem) or "case"


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    exit_code = 0
    for item in args.structures:
        source = Path(item)
        out = root / _safe_id(source)
        row = {"input": str(source), "output": str(out), "status": "ok", "error": ""}
        try:
            prepare_structure(source, out)
            build_report(out, title=f"Smoke report: {source.name}")
        except Exception as exc:  # noqa: BLE001 - batch summary records failures
            row["status"] = "failed"
            row["error"] = f"{exc.__class__.__name__}: {exc}"
            exit_code = 1
            if not args.continue_on_error:
                rows.append(row)
                break
        rows.append(row)

    csv_path = root / "summary.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["input", "output", "status", "error"])
        writer.writeheader()
        writer.writerows(rows)
    (root / "summary.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
