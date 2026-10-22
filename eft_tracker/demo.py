"""Synthetic demo data (no real clients). Writes into the *current* EFT_DATA_DIR."""
from __future__ import annotations

import random
from datetime import date, timedelta

from . import store

CASES = {"AB": 0, "CD": 3, "EF": 6}  # case -> week offset of first session


def _skill_curve(base: float, slope: float, n: int, rng: random.Random) -> int:
    return max(0, min(4, round(base + slope * n + rng.uniform(-0.6, 0.6))))


def build(seed: int = 7) -> int:
    rng = random.Random(seed)
    rubric = store.load_rubric()
    today = date.today()
    start = today - timedelta(weeks=14)
    base = {"tracking_reflecting": (2.0, .06), "validation": (2.3, .05), "alliance_safety": (2.2, .04),
            "cycle_reframing": (1.5, .09), "evocative_responding": (1.6, .08), "emotional_deepening": (1.0, .10),
            "heightening": (1.2, .07), "empathic_conjecture": (1.4, .07), "enactment_timing": (0.9, .10),
            "enactment_facilitation": (1.5, .07), "stage_pacing": (1.3, .06), "pacing_presence": (1.8, .05)}
    count = 0
    for case, off in CASES.items():
        for i in range(7 if case != "EF" else 5):
            d = start + timedelta(weeks=off + i * 1 + (0 if case == "AB" else 0), days=rng.randint(0, 2))
            if d > today:
                continue
            n = store.next_number(case)
            sid = store.session_id(case, d.isoformat(), n)
            true_step = min(9, 2 + int((i + (1 if case == "CD" else 0)) * 0.9))
            my_step = min(9, true_step + (2 if i < 5 else 1 if i < 8 else 0))
            skills = {}
            for k, (b, sl) in base.items():
                sc_ = _skill_curve(b, sl, count, rng)
                skills[k] = {"assessable": k != "pacing_presence" or rng.random() > .3, "score": sc_,
                             "confidence": round(rng.uniform(.5, .9), 2), "evidence": [],
                             "note": "Synthetic demo note."}
            enacts = []
            if true_step >= 3 and rng.random() < .8:
                enacts.append({"quote_of_invitation": "Can you tell her that, right now?",
                               "primary_emotion_accessed_before": rng.choice(["no", "partial", "yes"]),
                               "evidence_before": [], "timing": rng.choices(["premature", "ripe", "late"], [5, 2 + i // 2, 1])[0],
                               "rationale": "Synthetic.", "one_more_move": "Stay with the felt moment for two more turns."})
            changes = []
            if true_step >= 5 and rng.random() < .5:
                changes.append({"type": rng.choice(["withdrawer_reengagement", "blamer_softening"]),
                                "strength": rng.choice(["weak", "moderate", "moderate", "strong"]),
                                "quote": "I didn't know you were scared too.", "note": "Synthetic."})
            blocks = []
            if true_step <= 5:
                blocks.append({"block_type": rng.choice(["withdrawer_not_engaged", "cycle_not_tracked", "secondary_emotion_dominant", "content_focus"]),
                               "partner": "Partner A", "evidence": [], "confidence": round(rng.uniform(.4, .8), 2),
                               "suggested_move": "Track the moment the withdrawer goes quiet and name what happens just before."})
            analysis = {
                "stage_assessment": {"step": true_step, "confidence": .6, "evidence": [], "rationale": "Synthetic.",
                                     "what_would_indicate_next_step": "Synthetic."},
                "skills": skills,
                "cycle_naming": {"level": min(4, max(0, (count + rng.randint(-2, 2)) // 4)),
                                 "cycle_description": "When one pushes, the other shuts down, and the push gets harder.",
                                 "who_named_it": "therapist", "evidence": [], "what_blocked_naming": "Synthetic."},
                "partner_positions": [], "enactments": enacts, "change_events": changes, "blocks": blocks,
                "rewrites": [{"therapist_quote": "Why do you think you pull away?", "issue": "A 'why' question pulls for explanation.",
                              "alternative": "What happens inside you right then, just before you go quiet?"}],
                "top_strengths": ["Warm, steady presence"], "growth_edges": ["emotional_deepening", "enactment_timing"],
                "focus_for_next_session": "Stay three turns with the next moment of emotion before turning to the partner.",
                "limits_note": "Synthetic.",
            }
            analysis["stage_assessment"]["stage"] = 1 if true_step <= 4 else 2 if true_step <= 7 else 3
            sess = {"id": sid, "case": case, "date": d.isoformat(), "number": n, "status": "scored",
                    "my_stage": 1 if my_step <= 4 else 2 if my_step <= 7 else 3, "my_step": my_step,
                    "my_block": "He is withdrawing" if i < 4 else None, "notes": None,
                    "talk_stats": {"therapist_word_share": round(.46 - .012 * count + rng.uniform(-.03, .03), 3),
                                   "therapist_turns": 120, "mean_therapist_turn_words": round(34 - count * .8, 1),
                                   "long_therapist_turns_80w": max(0, 9 - count // 2),
                                   "therapist_question_rate": round(rng.uniform(.5, 1.1), 2),
                                   "client_speakers": ["Partner A", "Partner B"], "total_words": 7800},
                    "supervisor": None, "analysis": analysis,
                    "scoring": {"model": "demo", "mode": "demo", "scored_at": d.isoformat(), "quote_check": {"checked": 0, "verbatim_rate": None}}}
            if count % 4 == 1:
                sess["supervisor"] = {"step": max(1, true_step + rng.choice([0, 0, -1])),
                                      "skills": {"emotional_deepening": max(0, min(4, skills["emotional_deepening"]["score"] + rng.choice([-1, 0, 0]))),
                                                 "enactment_timing": max(0, min(4, skills["enactment_timing"]["score"] + rng.choice([-1, 0, 1]))),
                                                 "cycle_reframing": max(0, min(4, skills["cycle_reframing"]["score"] + rng.choice([0, 0, 1])))},
                                      "notes": "Synthetic supervisor ratings."}
                sess["supervisor"]["stage"] = 1 if sess["supervisor"]["step"] <= 4 else 2 if sess["supervisor"]["step"] <= 7 else 3
            store.save_session(sess)
            count += 1
    for w in range(0, 14):
        for _ in range(rng.choice([0, 1, 1, 2, 3]) if w > 3 else rng.choice([0, 0, 1])):
            store.log_practice(rng.choice(["emotional_deepening", "enactment_timing", "stage_pacing", "cycle_reframing"]),
                               rng.choice([10, 15, 15, 20]), "synthetic",
                               (start + timedelta(weeks=w, days=rng.randint(0, 6))).isoformat())
    return count
