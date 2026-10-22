"""Flat-file JSON store. Everything lives under one local data directory."""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path

RUBRIC_PATH = Path(__file__).with_name("rubric.json")


def data_dir() -> Path:
    d = Path(os.environ.get("EFT_DATA_DIR", "data")).resolve()
    for sub in ("sessions", "transcripts"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    return d


def load_rubric() -> dict:
    local = data_dir() / "rubric.local.json"  # per-user override, never committed
    path = local if local.exists() else RUBRIC_PATH
    return json.loads(path.read_text())


def _atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def slug(case: str) -> str:
    s = re.sub(r"[^A-Za-z0-9+_-]+", "", case.strip())
    if not s:
        raise ValueError("case id must contain letters or digits (use client initials)")
    return s.upper()


def session_id(case: str, d: str, n: int) -> str:
    return f"{slug(case)}_{d}_{n:02d}"


def _session_path(sid: str) -> Path:
    return data_dir() / "sessions" / f"{sid}.json"


def save_session(sess: dict) -> None:
    _atomic_write(_session_path(sess["id"]), json.dumps(sess, indent=2, ensure_ascii=False))


def load_session(sid: str) -> dict:
    p = _session_path(sid)
    if not p.exists():
        raise KeyError(f"no such session: {sid}")
    return json.loads(p.read_text())


def all_sessions() -> list[dict]:
    out = [json.loads(p.read_text()) for p in (data_dir() / "sessions").glob("*.json")]
    return sorted(out, key=lambda s: (s["date"], s["case"], s["number"]))


def next_number(case: str) -> int:
    return 1 + max([s["number"] for s in all_sessions() if s["case"] == slug(case)] or [0])


def transcript_path(sid: str) -> Path:
    return data_dir() / "transcripts" / f"{sid}.txt"


def load_cases() -> dict:
    p = data_dir() / "cases.json"
    return json.loads(p.read_text()) if p.exists() else {}


def save_cases(cases: dict) -> None:
    _atomic_write(data_dir() / "cases.json", json.dumps(cases, indent=2, ensure_ascii=False))


def log_practice(skill: str, minutes: int, note: str = "", d: str | None = None) -> dict:
    rec = {"date": d or date.today().isoformat(), "skill": skill, "minutes": int(minutes), "note": note,
           "logged_at": datetime.now().isoformat(timespec="seconds")}
    with open(data_dir() / "practice.jsonl", "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def load_practice() -> list[dict]:
    p = data_dir() / "practice.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
