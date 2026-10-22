"""Builds the scoring prompt from the rubric. Used by API mode and by manual (paste-into-Claude) mode."""
from __future__ import annotations

import json

SYSTEM = """You are an experienced Emotionally Focused Therapy (EFT) for couples supervisor reviewing a session transcript for a therapist in training who is working toward ICEEFT certification. You code the transcript against a fixed rubric and return JSON only.

Ground rules:
- Evidence first. Every score and claim must cite a short VERBATIM quote from the transcript (max ~25 words). Never invent or paraphrase quotes. If there is no evidence, say so.
- A transcript cannot show vocal tone, tempo, silence, facial expression or body language. Never claim to have observed them. If a skill depends on them, score only what the words support, set assessable=false when the words give you nothing, and lower confidence.
- Be a calibrated, candid rater, not a cheerleader. Use the full 0-4 scale. Most competent trainee sessions are 2-3 on most skills. A 4 is rare.
- Clients are identified only as Partner A / Partner B or by the labels in the transcript. Do not guess gender or identity.
- The therapist has asked for a rigorous read of three things in particular: (1) whether emotion was actually deepened before any enactment, (2) which EFT step the couple is really at and whether the therapist's own estimate is too advanced, and (3) whether and how the cycle was named by the clients.
- Your stage/step call is an independent estimate from the words alone, not a deference to the therapist's estimate. If you disagree with the therapist's estimate, say so plainly and explain with evidence.
- You are producing a screening aid for supervision, not a clinical determination. Flag uncertainty."""

OUTPUT_SPEC = """Return ONE JSON object and nothing else (no prose, no markdown fences) with exactly these keys:

{
  "stage_assessment": {
    "step": <integer 1-9, your best estimate of the step the COUPLE's process is at in this session>,
    "confidence": <number 0-1>,
    "evidence": [<verbatim quote>, ...],
    "rationale": "<2-3 sentences>",
    "what_would_indicate_next_step": "<what you'd need to see to call the next step>"
  },
  "skills": {
    "<skill_key>": {
      "assessable": <true|false>,
      "score": <integer 0-4; use 0 when assessable=false>,
      "confidence": <number 0-1>,
      "evidence": [<verbatim quote>, ...],
      "note": "<one or two sentences: what worked, what was missed>"
    }, ... one entry for EVERY skill key listed in the rubric
  },
  "cycle_naming": {
    "level": <integer 0-4 per the cycle_naming_levels>,
    "cycle_description": "<the cycle in 1-2 sentences, in the clients' own words where possible>",
    "who_named_it": "<therapist|partner_a|partner_b|both_partners|nobody>",
    "evidence": [<verbatim quote>, ...],
    "what_blocked_naming": "<why the clients did or did not name it; null if level>=3>"
  },
  "partner_positions": [
    {"partner": "<label>", "position": "<pursuer|withdrawer|both|unclear>", "secondary_emotion_seen": "<string or null>", "primary_emotion_signal": "<string or null, only if the words show it>"}
  ],
  "enactments": [
    {
      "quote_of_invitation": "<verbatim therapist invitation to turn to the partner>",
      "primary_emotion_accessed_before": "<yes|partial|no|unclear>",
      "evidence_before": [<verbatim quote(s) from the 2-4 turns before the invitation>],
      "timing": "<premature|ripe|late>",
      "rationale": "<1-2 sentences>",
      "one_more_move": "<if premature: the specific deepening move that was missing; else null>"
    }
  ],
  "change_events": [
    {"type": "<withdrawer_reengagement|blamer_softening|other_shift>", "strength": "<weak|moderate|strong>", "quote": "<verbatim>", "note": "<short>"}
  ],
  "blocks": [
    {"block_type": "<key from block_types>", "partner": "<label or both>", "evidence": [<verbatim quote>], "confidence": <number 0-1>, "suggested_move": "<concrete next-session intervention>"}
  ],
  "rewrites": [
    {"therapist_quote": "<verbatim therapist turn that was a missed opportunity>", "issue": "<short>", "alternative": "<what a stronger EFT response sounds like, in plain spoken language>"}
  ],
  "top_strengths": [<up to 3 short strings>],
  "growth_edges": [<up to 3 skill keys, most important first>],
  "focus_for_next_session": "<one concrete, practiceable focus>",
  "limits_note": "<what you could not assess from text alone>"
}

Rules: enactments may be an empty list if there were none. change_events may be empty. blocks: 0-3 items. rewrites: 1-3 items, only genuine missed opportunities."""


def build_user_prompt(rubric: dict, transcript: str, meta: dict) -> str:
    skills = [
        {k: s[k] for k in ("key", "name", "description", "look_for", "text_visibility")}
        for s in rubric["skills"]
    ]
    my = []
    if meta.get("my_step"):
        my.append(f"Therapist's own estimate of the couple's step: {meta['my_step']}")
    elif meta.get("my_stage"):
        my.append(f"Therapist's own estimate of the couple's stage: {meta['my_stage']}")
    if meta.get("my_block"):
        my.append(f"Therapist's own hypothesis about what is blocking the couple: {meta['my_block']}")
    if meta.get("notes"):
        my.append(f"Therapist's notes: {meta['notes']}")
    ctx = "\n".join(my) or "(none supplied)"
    return (
        f"## Session\nCase: {meta['case']}  |  Session #{meta['number']}  |  Date: {meta['date']}\n\n"
        f"## Therapist-supplied context (do not defer to it)\n{ctx}\n\n"
        f"## Rubric\nScore scale: {json.dumps(rubric['score_scale'])}\n"
        f"EFT steps: {json.dumps(rubric['steps'])}\n"
        f"Cycle-naming levels: {json.dumps(rubric['cycle_naming_levels'])}\n"
        f"Block types: {json.dumps(rubric['block_types'])}\n"
        f"Skills: {json.dumps(skills)}\n\n"
        f"## Output format\n{OUTPUT_SPEC}\n\n"
        f"## Transcript\n<transcript>\n{transcript}\n</transcript>"
    )
