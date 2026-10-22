"""Scoring: API mode (Anthropic SDK) and manual mode (import JSON the therapist pasted back)."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime

from . import prompts

DEFAULT_MODEL = "claude-opus-5-5"
MAX_TOKENS = 32000


class ScoreError(Exception):
    pass


def extract_json(text: str) -> dict:
    """Pull the first top-level JSON object out of model output (tolerates stray fences/prose)."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start = text.find("{")
    if start < 0:
        raise ScoreError("no JSON object found in output")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError as e:
                    raise ScoreError(f"invalid JSON: {e}") from e
    raise ScoreError("unterminated JSON object (output may have been truncated)")


def _num(v, lo, hi, what):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ScoreError(f"{what} must be a number, got {v!r}")
    if not lo <= v <= hi:
        raise ScoreError(f"{what} out of range {lo}-{hi}: {v}")
    return v


def validate(analysis: dict, rubric: dict) -> dict:
    """Strict-enough validation; normalizes optional lists. Raises ScoreError with a fixable message."""
    a = analysis
    st = a.get("stage_assessment")
    if not isinstance(st, dict):
        raise ScoreError("missing stage_assessment")
    st["step"] = int(_num(st.get("step"), 1, 9, "stage_assessment.step"))
    st["stage"] = 1 if st["step"] <= 4 else 2 if st["step"] <= 7 else 3
    st["confidence"] = _num(st.get("confidence", 0.5), 0, 1, "stage_assessment.confidence")
    keys = [s["key"] for s in rubric["skills"]]
    skills = a.get("skills")
    if not isinstance(skills, dict):
        raise ScoreError("missing skills")
    missing = [k for k in keys if k not in skills]
    if missing:
        raise ScoreError(f"missing skill entries: {', '.join(missing)}")
    for k in keys:
        s = skills[k]
        s["assessable"] = bool(s.get("assessable", True))
        s["score"] = int(_num(s.get("score", 0), 0, 4, f"skills.{k}.score"))
        s["confidence"] = _num(s.get("confidence", 0.5), 0, 1, f"skills.{k}.confidence")
        s.setdefault("evidence", [])
        s.setdefault("note", "")
    for extra in set(skills) - set(keys):
        del skills[extra]
    cn = a.get("cycle_naming")
    if not isinstance(cn, dict):
        raise ScoreError("missing cycle_naming")
    cn["level"] = int(_num(cn.get("level"), 0, 4, "cycle_naming.level"))
    for lst in ("partner_positions", "enactments", "change_events", "blocks", "rewrites",
                "top_strengths", "growth_edges"):
        a[lst] = a.get(lst) or []
    for e in a["enactments"]:
        if e.get("timing") not in ("premature", "ripe", "late"):
            raise ScoreError(f"enactment timing must be premature|ripe|late, got {e.get('timing')!r}")
    for b in a["blocks"]:
        if b.get("block_type") not in rubric["block_types"]:
            b["block_type"] = "other"
    a["growth_edges"] = [g for g in a["growth_edges"] if g in keys][:3]
    return a


def quote_check(analysis: dict, transcript: str) -> dict:
    """Fraction of cited quotes that appear verbatim in the transcript (whitespace/case-insensitive).
    Cheap hallucination tripwire; surfaced on the dashboard."""
    norm = lambda s: re.sub(r"\s+", " ", re.sub(r"[\"'“”‘’]", "", s)).strip().lower()  # noqa: E731
    hay = norm(transcript)
    quotes: list[str] = []
    for s in analysis["skills"].values():
        quotes += [q for q in s.get("evidence", []) if isinstance(q, str)]
    quotes += [q for q in analysis["stage_assessment"].get("evidence", []) if isinstance(q, str)]
    quotes += [q for q in analysis["cycle_naming"].get("evidence", []) if isinstance(q, str)]
    quotes += [c.get("quote", "") for c in analysis["change_events"]]
    quotes += [r.get("therapist_quote", "") for r in analysis["rewrites"]]
    quotes = [q for q in quotes if q and q.strip()]
    if not quotes:
        return {"checked": 0, "verbatim_rate": None}
    ok = sum(1 for q in quotes if norm(q).rstrip(".…") in hay)
    return {"checked": len(quotes), "verbatim_rate": round(ok / len(quotes), 3)}


def apply_analysis(sess: dict, raw: dict, rubric: dict, transcript: str, model: str, mode: str) -> dict:
    analysis = validate(raw, rubric)
    sess["analysis"] = analysis
    sess["status"] = "scored"
    sess["scoring"] = {"model": model, "mode": mode, "scored_at": datetime.now().isoformat(timespec="seconds"),
                       "quote_check": quote_check(analysis, transcript)}
    return sess


def call_model(user_prompt: str, model: str | None = None, client=None) -> tuple[str, str]:
    """One streamed request. Returns (text, model_used). Raises ScoreError on refusal/truncation."""
    model = model or os.environ.get("EFT_MODEL", DEFAULT_MODEL)
    if client is None:
        try:
            import anthropic
        except ImportError as e:  # pragma: no cover
            raise ScoreError("`pip install anthropic` or use manual mode (`prompt` / `import`)") from e
        client = anthropic.Anthropic()
    with client.messages.stream(
        model=model,
        max_tokens=MAX_TOKENS,
        system=prompts.SYSTEM,
        output_config={"effort": "high"},
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise ScoreError("the model declined this request; use manual mode or try again")
    if msg.stop_reason == "max_tokens":
        raise ScoreError("output truncated at max_tokens")
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    return text, model


def score_with_api(sess: dict, transcript_seen: str, rubric: dict,
                   model: str | None = None, client=None, retries: int = 1) -> dict:
    prompt = prompts.build_user_prompt(rubric, transcript_seen, sess)
    last: Exception | None = None
    for attempt in range(retries + 1):
        text, used = call_model(prompt, model, client)
        try:
            return apply_analysis(sess, extract_json(text), rubric, transcript_seen, used, "api")
        except ScoreError as e:
            last = e
            prompt += f"\n\n(Your previous output was rejected: {e}. Return the complete corrected JSON object only.)"
    raise ScoreError(f"model output failed validation after {retries + 1} attempts: {last}")
