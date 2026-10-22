"""Transcript parsing and local (no-LLM) talk statistics."""
from __future__ import annotations

import re

TURN_RE = re.compile(r"^\s*(?:\[?\d{1,2}:\d{2}(?::\d{2})?\]?\s*)?([A-Za-z][\w .'\-]{0,30}?):\s+(\S.*)$")
THERAPIST_DEFAULTS = {"me", "therapist", "counselor", "clinician"}


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
        "client_speakers": sorted({s for s, _ in turns if s.lower() not in labels}),
        "total_words": tw + cw,
    }
