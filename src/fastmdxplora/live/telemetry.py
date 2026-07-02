"""File-backed telemetry for local simulation monitoring."""

from __future__ import annotations

import csv
import json
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATUS_FILE = "live_status.json"
METRICS_FILE = "live_metrics.csv"
EVENTS_FILE = "live_events.log"

METRIC_FIELDS = [
    "timestamp",
    "stage",
    "step",
    "simulation_time_ns",
    "potential_energy",
    "kinetic_energy",
    "total_energy",
    "temperature",
    "volume",
    "density",
    "progress_percent",
]

NUMERIC_METRIC_FIELDS = [field for field in METRIC_FIELDS if field != "timestamp" and field != "stage"]

NORMAL_EXPLANATION = "Simulation is progressing normally."
NUMERIC_EXPLANATION = (
    "The simulation became numerically unstable. This usually means the timestep "
    "is too large, the starting structure has clashes, the temperature is too high, "
    "or equilibration was not gentle enough."
)
ENERGY_EXPLANATION = (
    "Energy increased sharply. This can indicate steric clashes, unstable timestep, "
    "bad contacts, or pressure/temperature coupling issues."
)
TEMPERATURE_EXPLANATION = (
    "Temperature is outside the expected range. Consider a smaller timestep, stronger "
    "friction, gentler heating, or checking the input structure."
)
STALE_EXPLANATION = (
    "No telemetry update has been seen recently. The simulation may be slow, paused, "
    "or crashed."
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _simulation_dir(path: str | Path) -> Path:
    root = Path(path)
    return root if root.name == "simulation" else root / "simulation"


@dataclass
class TelemetryWriter:
    """Write live status, metrics, and event files without failing the run."""

    simulation_dir: str | Path
    enabled: bool = True
    total_steps: int | None = None
    planned_frames: int | None = None
    timestep_fs: float | None = None
    platform: str | None = None
    target_temperature_K: float | None = None
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    _last_status: dict[str, Any] = field(default_factory=dict, init=False)

    @property
    def root(self) -> Path:
        return Path(self.simulation_dir)

    @property
    def status_path(self) -> Path:
        return self.root / STATUS_FILE

    @property
    def metrics_path(self) -> Path:
        return self.root / METRICS_FILE

    @property
    def events_path(self) -> Path:
        return self.root / EVENTS_FILE

    def write_status(self, **updates: Any) -> None:
        if not self.enabled:
            return
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            now = datetime.now(timezone.utc)
            status = {
                "stage": "not available",
                "status": "running",
                "current_step": None,
                "total_planned_steps": self.total_steps,
                "current_frame_count": None,
                "planned_frame_count": self.planned_frames,
                "elapsed_wall_time_s": round((now - self.start_time).total_seconds(), 3),
                "simulation_time_completed_ns": None,
                "timestep_fs": self.timestep_fs,
                "platform": self.platform,
                "target_temperature_K": self.target_temperature_K,
                "last_update_timestamp": _utc_now(),
                "current_checkpoint_path": None,
                "latest_warning": None,
                "latest_error": None,
            }
            status.update(self._last_status)
            status.update({k: v for k, v in updates.items() if v is not None})
            status["elapsed_wall_time_s"] = round((now - self.start_time).total_seconds(), 3)
            status["last_update_timestamp"] = _utc_now()
            self._last_status = dict(status)
            tmp = self.status_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(status, indent=2, default=str), encoding="utf-8")
            os.replace(tmp, self.status_path)
        except Exception:
            return

    def append_metric(self, **row: Any) -> None:
        if not self.enabled:
            return
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            exists = self.metrics_path.exists()
            clean_row = {field: row.get(field, "") for field in METRIC_FIELDS}
            clean_row["timestamp"] = clean_row["timestamp"] or _utc_now()
            with self.metrics_path.open("a", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=METRIC_FIELDS)
                if not exists:
                    writer.writeheader()
                writer.writerow(clean_row)
        except Exception:
            return

    def event(self, message: str, *, level: str = "info") -> None:
        if not self.enabled:
            return
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            with self.events_path.open("a", encoding="utf-8") as fh:
                fh.write(f"{_utc_now()}\t{level}\t{message}\n")
        except Exception:
            return


def read_status(project_root: str | Path) -> dict[str, Any]:
    path = _simulation_dir(project_root) / STATUS_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def read_metrics(project_root: str | Path, *, limit: int = 500) -> list[dict[str, Any]]:
    path = _simulation_dir(project_root) / METRICS_FILE
    try:
        with path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
    except OSError:
        return []
    return rows[-limit:]


def read_events(project_root: str | Path, *, limit: int = 100) -> list[dict[str, str]]:
    path = _simulation_dir(project_root) / EVENTS_FILE
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    events: list[dict[str, str]] = []
    for line in lines[-limit:]:
        parts = line.split("\t", 2)
        if len(parts) == 3:
            events.append({"timestamp": parts[0], "level": parts[1], "message": parts[2]})
        else:
            events.append({"timestamp": "", "level": "info", "message": line})
    return events


def analyze_health(
    status: dict[str, Any],
    metrics: list[dict[str, Any]],
    *,
    stale_after_seconds: float = 90.0,
) -> dict[str, str]:
    """Classify the latest telemetry into ok/warning/failed with plain text."""
    latest_error = status.get("latest_error")
    if latest_error or str(status.get("status", "")).lower() == "failed":
        return {
            "state": "failed",
            "message": str(latest_error or "Simulation failed."),
            "explanation": NUMERIC_EXPLANATION,
        }

    latest = metrics[-1] if metrics else {}
    for field_name in NUMERIC_METRIC_FIELDS:
        value = _safe_float(latest.get(field_name))
        if value is not None and not math.isfinite(value):
            return {
                "state": "failed",
                "message": f"{field_name} is NaN or infinite.",
                "explanation": NUMERIC_EXPLANATION,
            }

    energy_state = _detect_energy_spike(metrics)
    if energy_state is not None:
        return energy_state

    temp = _safe_float(latest.get("temperature"))
    target = _safe_float(status.get("target_temperature_K"))
    if temp is not None:
        if not math.isfinite(temp):
            return {
                "state": "failed",
                "message": "Temperature is NaN or infinite.",
                "explanation": NUMERIC_EXPLANATION,
            }
        if target is not None and abs(temp - target) > max(50.0, target * 0.25):
            return {
                "state": "warning",
                "message": f"Temperature {temp:.1f} K is far from target {target:.1f} K.",
                "explanation": TEMPERATURE_EXPLANATION,
            }
        if target is None and temp > 450.0:
            return {
                "state": "warning",
                "message": f"Temperature is high ({temp:.1f} K).",
                "explanation": TEMPERATURE_EXPLANATION,
            }

    timestamp = status.get("last_update_timestamp")
    if str(status.get("status", "")).lower() == "running" and timestamp:
        age = _timestamp_age_seconds(str(timestamp))
        if age is not None and age > stale_after_seconds:
            return {
                "state": "warning",
                "message": "Telemetry is stale.",
                "explanation": STALE_EXPLANATION,
            }

    if status:
        return {"state": "ok", "message": "Normal progress", "explanation": NORMAL_EXPLANATION}
    return {
        "state": "unknown",
        "message": "Live telemetry is not available.",
        "explanation": (
            "Live simulation telemetry was not recorded for this run. Start "
            "fastmdx dashboard serve --output ... during a simulation to monitor progress."
        ),
    }


def _detect_energy_spike(metrics: list[dict[str, Any]]) -> dict[str, str] | None:
    if len(metrics) < 2:
        return None
    field_name = "total_energy"
    prev = _safe_float(metrics[-2].get(field_name))
    current = _safe_float(metrics[-1].get(field_name))
    if prev is None or current is None:
        field_name = "potential_energy"
        prev = _safe_float(metrics[-2].get(field_name))
        current = _safe_float(metrics[-1].get(field_name))
    if prev is None or current is None:
        return None
    if not (math.isfinite(prev) and math.isfinite(current)):
        return {
            "state": "failed",
            "message": f"{field_name} is NaN or infinite.",
            "explanation": NUMERIC_EXPLANATION,
        }
    delta = abs(current - prev)
    threshold = max(10000.0, abs(prev) * 5.0)
    if delta > threshold:
        return {
            "state": "warning",
            "message": f"{field_name} changed sharply ({prev:.3g} to {current:.3g}).",
            "explanation": ENERGY_EXPLANATION,
        }
    return None


def _timestamp_age_seconds(value: str) -> float | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds()
