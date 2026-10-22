"""Progress, XP, levels, streaks, badges, quests, calibration. Pure functions over stored data."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from statistics import mean

LEVELS = [  # (cumulative XP, title)
    (0, "Cycle Spotter"), (150, "Process Tracker"), (400, "Emotion Tender"), (800, "Enactment Guide"),
    (1400, "Softening Witness"), (2200, "Bond Weaver"), (3300, "Practice Master"), (4800, "Supervisor-in-Training"),
]
# Volume earns little by design: XP should follow deliberate practice, calibration and real improvement.
XP_LOGGED, XP_SCORED, XP_CALIBRATION, XP_LEVELUP, XP_PER_PRACTICE_MIN, XP_PRACTICE_CAP_MIN = 5, 10, 60, 25, 3, 30
SKILL_MILESTONES = (2.0, 2.5, 3.0, 3.5)  # rolling-3 thresholds that each pay XP_LEVELUP once per skill
XP_SESSION_WEEKLY_CAP = 5  # sessions per ISO week that earn session XP
ROLL = 3  # rolling window (sessions)


def _d(s: str) -> date:
    return date.fromisoformat(s)


def level_for(xp: int) -> dict:
    idx = max(i for i, (th, _) in enumerate(LEVELS) if xp >= th)
    nxt = LEVELS[idx + 1] if idx + 1 < len(LEVELS) else None
    return {"level": idx + 1, "title": LEVELS[idx][1], "xp": xp, "floor": LEVELS[idx][0],
            "next_at": nxt[0] if nxt else None, "next_title": nxt[1] if nxt else None}


def scored(sessions: list[dict]) -> list[dict]:
    return [s for s in sessions if s.get("status") == "scored" and s.get("analysis")]


def skill_series(sessions: list[dict], key: str) -> list[dict]:
    out = []
    for s in scored(sessions):
        sk = s["analysis"]["skills"].get(key)
        if sk and sk.get("assessable", True):
            out.append({"date": s["date"], "session": s["id"], "case": s["case"], "score": sk["score"]})
    return out


def _roll(vals: list[float], end: int) -> float | None:
    w = vals[max(0, end - ROLL):end]
    return mean(w) if w else None


def skill_summary(sessions: list[dict], rubric: dict) -> list[dict]:
    rows = []
    for sk in rubric["skills"]:
        ser = skill_series(sessions, sk["key"])
        vals = [p["score"] for p in ser]
        cur = _roll(vals, len(vals))
        prev = _roll(vals, len(vals) - ROLL) if len(vals) > ROLL else None
        best = max(_roll(vals, i) for i in range(1, len(vals) + 1)) if vals else None
        rows.append({"key": sk["key"], "name": sk["name"], "group": sk["group"], "text_visibility": sk["text_visibility"],
                     "focus_block": bool(sk.get("focus_block")), "n": len(vals),
                     "current": round(cur, 2) if cur is not None else None,
                     "previous": round(prev, 2) if prev is not None else None,
                     "best": round(best, 2) if best is not None else None,
                     "series": ser})
    return rows


def reference_stage(s: dict) -> dict | None:
    """Supervisor's call beats the model's. Returns {'stage','step','source'} or None."""
    sup = s.get("supervisor") or {}
    if sup.get("step") or sup.get("stage"):
        step = sup.get("step")
        stage = sup.get("stage") or (1 if step <= 4 else 2 if step <= 7 else 3)
        return {"stage": stage, "step": step, "source": "supervisor"}
    a = s.get("analysis")
    if a:
        return {"stage": a["stage_assessment"]["stage"], "step": a["stage_assessment"]["step"], "source": "model"}
    return None


def stage_calibration(sessions: list[dict]) -> dict:
    """How accurate / how biased is the therapist's own stage call vs. the reference?"""
    rows = []
    for s in sessions:
        mine = s.get("my_stage")
        ref = reference_stage(s)
        if mine and ref:
            rows.append({"session": s["id"], "date": s["date"], "case": s["case"], "mine": mine, "ref": ref["stage"],
                         "ref_step": ref["step"], "my_step": s.get("my_step"), "source": ref["source"],
                         "err": mine - ref["stage"]})
    errs = [r["err"] for r in rows]
    recent = rows[-5:]
    return {"rows": rows, "n": len(rows),
            "match_rate": round(sum(1 for e in errs if e == 0) / len(errs), 2) if errs else None,
            "recent_match_rate": round(sum(1 for r in recent if r["err"] == 0) / len(recent), 2) if recent else None,
            "bias": round(mean(errs), 2) if errs else None,  # >0: you call it more advanced than the reference
            "over_advanced": sum(1 for e in errs if e > 0), "under_advanced": sum(1 for e in errs if e < 0)}


def scorer_trust(sessions: list[dict], rubric: dict) -> dict:
    """Agreement between the model's skill scores and the supervisor's, on sessions the supervisor rated."""
    diffs, per_skill = [], {}
    stage_hits = stage_n = 0
    for s in scored(sessions):
        sup = s.get("supervisor")
        if not sup:
            continue
        for k, v in (sup.get("skills") or {}).items():
            m = s["analysis"]["skills"].get(k)
            if m and m.get("assessable", True):
                d = m["score"] - v
                diffs.append(abs(d))
                per_skill.setdefault(k, []).append(d)
        if sup.get("step") or sup.get("stage"):
            stage_n += 1
            stage_hits += reference_stage(s)["stage"] == s["analysis"]["stage_assessment"]["stage"]
    names = {x["key"]: x["name"] for x in rubric["skills"]}
    return {"direction": direction_agreement(sessions),
            "calibrated_sessions": len([s for s in sessions if s.get("supervisor")]),
            "n_ratings": len(diffs), "mae": round(mean(diffs), 2) if diffs else None,
            "stage_agreement": round(stage_hits / stage_n, 2) if stage_n else None, "stage_n": stage_n,
            "per_skill": [{"key": k, "name": names.get(k, k), "mean_diff": round(mean(v), 2), "n": len(v)}
                          for k, v in sorted(per_skill.items())]}


def direction_agreement(sessions: list[dict]) -> dict:
    """Does the scorer agree in DIRECTION with what the supervisor said in supervision?
    growth_edge agrees if the scorer gave that skill <=2 or listed it among its growth edges;
    strength agrees if the scorer gave it >=3. Much weaker than numeric ratings, but needs none."""
    hits = n = 0
    rows = []
    for s in scored(sessions):
        for sig in (s.get("supervision") or {}).get("skill_signals", []):
            m = s["analysis"]["skills"].get(sig["skill"])
            if not m or not m.get("assessable", True):
                continue
            edge = m["score"] <= 2 or sig["skill"] in s["analysis"].get("growth_edges", [])
            ok = edge if sig["signal"] == "growth_edge" else m["score"] >= 3
            n += 1
            hits += ok
            rows.append({"session": s["id"], "skill": sig["skill"], "supervisor": sig["signal"], "scorer": m["score"], "agree": ok})
    return {"n": n, "agree": hits, "rate": round(hits / n, 2) if n else None, "rows": rows,
            "sessions": len([s for s in sessions if s.get("supervision")])}


def iso_week(d: date) -> tuple[int, int]:
    y, w, _ = d.isocalendar()
    return (y, w)


def streak_weeks(active_days: set[date], today: date) -> int:
    weeks = {iso_week(d) for d in active_days}
    cur, n = iso_week(today), 0
    if cur not in weeks:  # current week is still open
        cur = iso_week(today - timedelta(days=7))
    while cur in weeks:
        n += 1
        y, w = cur
        cur = iso_week(date.fromisocalendar(y, w, 1) - timedelta(days=7))
    return n


def xp_ledger(sessions: list[dict], practice: list[dict], skills: list[dict]) -> dict:
    wk_logged: dict[tuple, int] = {}
    wk_scored: dict[tuple, int] = {}
    for s in sessions:
        w = iso_week(_d(s["date"]))
        wk_logged[w] = wk_logged.get(w, 0) + 1
        if s.get("status") == "scored":
            wk_scored[w] = wk_scored.get(w, 0) + 1
    cap = lambda d: sum(min(v, XP_SESSION_WEEKLY_CAP) for v in d.values())  # noqa: E731
    parts = {"sessions_logged": XP_LOGGED * cap(wk_logged), "sessions_scored": XP_SCORED * cap(wk_scored),
             "calibration": XP_CALIBRATION * len([s for s in sessions if s.get("supervisor")])}
    per_day: dict[str, int] = {}
    for p in practice:
        per_day[p["date"]] = per_day.get(p["date"], 0) + p["minutes"]
    parts["practice"] = sum(min(m, XP_PRACTICE_CAP_MIN) * XP_PER_PRACTICE_MIN for m in per_day.values())
    ups = 0  # one award per skill per milestone, so noisy session-to-session swings can't farm XP
    for sk in skills:
        vals = [p["score"] for p in sk["series"]]
        top = max([_roll(vals, i) for i in range(ROLL, len(vals) + 1)] or [0])
        ups += sum(1 for m in SKILL_MILESTONES if top >= m)
    parts["improvement"] = XP_LEVELUP * ups
    return {"parts": parts, "total": sum(parts.values())}


def badges(sessions: list[dict], practice: list[dict], skills: list[dict], cal: dict, trust: dict) -> list[dict]:
    sc = scored(sessions)
    sk = {s["key"]: s for s in skills}
    enacts = [e for s in sc for e in s["analysis"]["enactments"]]
    changes = [c for s in sc for c in s["analysis"]["change_events"] if c.get("strength") in ("moderate", "strong")]
    by_week: dict[tuple, set] = {}
    for p in practice:
        by_week.setdefault(iso_week(_d(p["date"])), set()).add(p["date"])
    seq = [r["err"] == 0 for r in cal["rows"]]
    run = best_run = 0
    for ok in seq:
        run = run + 1 if ok else 0
        best_run = max(best_run, run)
    ripe_ct = sum(1 for e in enacts if e["timing"] == "ripe")
    maxcyc = max([s["analysis"]["cycle_naming"]["level"] for s in sc] or [0])
    defs = [
        ("first_score", "First Read", "Score your first session", len(sc) >= 1),
        ("five", "Five Tapes", "5 scored sessions", len(sc) >= 5),
        ("twentyfive", "Quarter Century", "25 scored sessions", len(sc) >= 25),
        ("cycle3", "Cycle Namer", "Clients used the cycle language themselves (level 3)", maxcyc >= 3),
        ("cycle4", "Cycle Whisperer", "Clients caught the cycle in real time (level 4)", maxcyc >= 4),
        ("softening", "Witness to a Shift", "A moderate+ withdrawer re-engagement or blamer softening", len(changes) >= 1),
        ("ripe2", "Ripe Timing", "2 enactments timed 'ripe'", ripe_ct >= 2),
        ("deepener", "Stay With It", "Deepening emotion rolling score 3.0+", (sk["emotional_deepening"]["current"] or 0) >= 3),
        ("stage3", "Stage Sniper", "3 stage calls in a row matching the reference", best_run >= 3),
        ("practice3", "Reps Over Reflection", "Practice on 3 different days in one week", any(len(v) >= 3 for v in by_week.values())),
        ("calibrated", "Trust But Verify", "3+ supervisor-rated sessions, scorer within 0.75 of supervisor", trust["calibrated_sessions"] >= 3 and (trust["mae"] or 9) <= 0.75),
    ]
    return [{"key": k, "name": n, "how": h, "earned": bool(e)} for k, n, h, e in defs]


def quests(skills: list[dict], rubric: dict, practice: list[dict], today: date) -> list[dict]:
    wk = iso_week(today)
    reps = sum(1 for p in practice if iso_week(_d(p["date"])) == wk)
    rated = [s for s in skills if s["current"] is not None]
    # Weakest first; the therapist's named blocks win ties.
    rated.sort(key=lambda s: (s["current"], 0 if s["focus_block"] else 1))
    out = []
    for s in rated[:2]:
        drills = rubric.get("drills", {}).get(s["key"], [])
        out.append({"kind": "skill", "skill": s["key"], "name": s["name"], "current": s["current"],
                    "target": min(4.0, round(s["current"] + 0.5, 1)), "drill": drills[0] if drills else None,
                    "xp": 20 + XP_PER_PRACTICE_MIN * (drills[0]["minutes"] if drills else 10),
                    "log_cmd": f"python -m eft_tracker practice {s['key']} --minutes {(drills[0]['minutes'] if drills else 10)}"})
    out.append({"kind": "weekly", "name": "Three practice reps this week", "progress": min(reps, 3), "goal": 3, "xp": 40})
    return out


def block_summary(sessions: list[dict]) -> dict:
    """Latest + trend for the therapist's named sticking points, from stored analyses."""
    sc = scored(sessions)
    enacts = [(s["date"], e) for s in sc for e in s["analysis"]["enactments"]]
    timing = {t: sum(1 for _, e in enacts if e["timing"] == t) for t in ("premature", "ripe", "late")}
    cyc = [{"date": s["date"], "case": s["case"], "level": s["analysis"]["cycle_naming"]["level"]} for s in sc]
    by_case: dict[str, dict] = {}
    for s in sc:
        by_case[s["case"]] = s
    return {"enactment_timing": timing, "enactment_n": len(enacts), "cycle_series": cyc,
            "latest_cycle_by_case": {c: s["analysis"]["cycle_naming"]["level"] for c, s in by_case.items()}}


def case_views(sessions: list[dict]) -> list[dict]:
    out = []
    for case in sorted({s["case"] for s in sessions}):
        ss = [s for s in sessions if s["case"] == case]
        sc = scored(ss)
        traj = [{"date": s["date"], "number": s["number"], "model_step": s["analysis"]["stage_assessment"]["step"],
                 "my_step": s.get("my_step"), "my_stage": s.get("my_stage"),
                 "cycle": s["analysis"]["cycle_naming"]["level"]} for s in sc]
        last = sc[-1]["analysis"] if sc else None
        out.append({"case": case, "sessions": len(ss), "scored": len(sc), "trajectory": traj,
                    "latest_blocks": (last or {}).get("blocks", []), "latest_focus": (last or {}).get("focus_for_next_session"),
                    "cycle_description": (last or {}).get("cycle_naming", {}).get("cycle_description"),
                    "change_events": [{"date": s["date"], **c} for s in sc for c in s["analysis"]["change_events"]]})
    return out


def build_dashboard_data(sessions: list[dict], practice: list[dict], rubric: dict, today: date | None = None) -> dict:
    today = today or date.today()
    skills = skill_summary(sessions, rubric)
    cal = stage_calibration(sessions)
    trust = scorer_trust(sessions, rubric)
    ledger = xp_ledger(sessions, practice, skills)
    active = {_d(s["date"]) for s in sessions} | {_d(p["date"]) for p in practice}
    rated_now = [s["current"] for s in skills if s["current"] is not None and s["text_visibility"] != "low"]
    rated_prev = [s["previous"] for s in skills if s["previous"] is not None and s["text_visibility"] != "low"]
    sess_out = []
    for s in sessions:
        sess_out.append({k: s.get(k) for k in ("id", "case", "date", "number", "status", "my_stage", "my_step", "my_block",
                                                "talk_stats", "supervisor", "supervision", "analysis", "scoring")})
    return {
        "generated": datetime.now().isoformat(timespec="minutes"),
        "level": level_for(ledger["total"]), "xp": ledger,
        "streak_weeks": streak_weeks(active, today),
        "overall": {"current": round(mean(rated_now), 2) if rated_now else None,
                    "previous": round(mean(rated_prev), 2) if rated_prev else None},
        "counts": {"sessions": len(sessions), "scored": len(scored(sessions)), "practice_entries": len(practice),
                   "practice_minutes": sum(p["minutes"] for p in practice)},
        "skills": skills, "stage": cal, "trust": trust, "blocks": block_summary(sessions),
        "badges": badges(sessions, practice, skills, cal, trust),
        "quests": quests(skills, rubric, practice, today), "cases": case_views(sessions),
        "sessions": sess_out, "rubric": {"steps": rubric["steps"], "cycle_levels": rubric["cycle_naming_levels"],
                                         "block_types": rubric["block_types"], "scale": rubric["score_scale"],
                                         "drills": rubric.get("drills", {})},
        "practice": practice[-60:],
    }
