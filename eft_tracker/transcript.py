"""Transcript parsing and local (no-LLM) talk statistics."""
from __future__ import annotations

import re
from datetime import date, datetime

TURN_RE = re.compile(r"^\s*(?:\[?\d{1,2}:\d{2}(?::\d{2})?\]?\s*)?([A-Za-z][\w .'\-]{0,30}?):\s+(\S.*)$")
THERAPIST_DEFAULTS = {"me", "therapist", "counselor", "clinician"}


HEADER_RE = re.compile(r"^\s*(Meeting Title|Title|Date|Meeting participants|Participants)\s*:\s*(.*)$", re.I)


def split_granola_header(text: str) -> tuple[dict, str]:
    """Granola exports start with 'Meeting Title / Date / Meeting participants / Transcript:'.
    Returns ({lowercased header: value}, body). Text with no such header comes back unchanged.
    The title often names the clients, so callers should drop it rather than forward it."""
    lines = text.splitlines()
    header: dict[str, str] = {}
    for i, line in enumerate(lines[:15]):
        if line.strip().lower() == "transcript:":
            return header, "\n".join(lines[i + 1:]).lstrip("\n")
        m = HEADER_RE.match(line)
        if m:
            header[m.group(1).lower()] = m.group(2).strip()
        elif line.strip():
            break
    return {}, text


def parse_header_date(value: str | None, today: date | None = None) -> str | None:
    """'Oct 21' / 'October 21, 2026' / '2026-10-21' -> ISO date. Yearless dates never land in the future."""
    if not value:
        return None
    today = today or date.today()
    v = value.strip().rstrip(".")
    for fmt in ("%Y-%m-%d", "%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y"):
        try:
            return datetime.strptime(v, fmt).date().isoformat()
        except ValueError:
            pass
    for fmt in ("%b %d %Y", "%B %d %Y"):
        try:
            d = datetime.strptime(f"{v} {today.year}", fmt).date()
        except ValueError:
            continue
        return (d.replace(year=today.year - 1) if d > today else d).isoformat()
    return None


def parse_turns(text: str) -> list[tuple[str, str]]:
    """Return [(speaker, utterance)]. Continuation lines attach to the previous turn."""
    turns: list[tuple[str, str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        m = TURN_RE.match(line)
        if m:
            turns.append((m.group(1).strip(), m.group(2).strip()))
        elif turns:
            turns[-1] = (turns[-1][0], turns[-1][1] + " " + line.strip())
    return turns


def talk_stats(text: str, therapist_label: str | None = None) -> dict | None:
    """Therapist talk-share, turn length, question rate. None if speakers can't be identified."""
    turns = parse_turns(text)
    if len(turns) < 6:
        return None
    labels = {therapist_label.lower()} if therapist_label else THERAPIST_DEFAULTS
    speakers = {s.lower() for s, _ in turns}
    if not labels & speakers:
        return None
    t = [u for s, u in turns if s.lower() in labels]
    c = [u for s, u in turns if s.lower() not in labels]
    client_speakers = sorted({s for s, _ in turns if s.lower() not in labels})
    words = lambda us: sum(len(u.split()) for u in us)  # noqa: E731
    tw, cw = words(t), words(c)
    if tw + cw == 0 or not t:
        return None
    return {
        "therapist_word_share": round(tw / (tw + cw), 3),
        "therapist_turns": len(t),
        "mean_therapist_turn_words": round(tw / len(t), 1),
        "long_therapist_turns_80w": sum(1 for u in t if len(u.split()) > 80),
        "therapist_question_rate": round(sum(u.count("?") for u in t) / len(t), 2),
        "client_speakers": client_speakers,
        # Granola often labels everyone who isn't you "Them": both partners in one stream.
        "partner_attribution": "merged" if len(client_speakers) == 1 else "separate",
        "total_words": tw + cw,
    }
