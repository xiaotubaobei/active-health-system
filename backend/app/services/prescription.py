"""Prescription state machine aligned with 申请书图15."""
from .catalog import load_prescription_libs, resolve_exercises

STATUS_FLOW = [
    "clinical_intake",
    "fitness_assessed",
    "pre_prescription",
    "monitoring",
    "formal_prescription",
    "implementing",
    "feedback",
]


def next_status(current: str) -> str:
    if current not in STATUS_FLOW:
        return STATUS_FLOW[0]
    i = STATUS_FLOW.index(current)
    return STATUS_FLOW[min(i + 1, len(STATUS_FLOW) - 1)]


def pick_template(age_group: str, goal: str, chronic_tags: list | None = None) -> tuple[str, dict]:
    libs = load_prescription_libs()
    chronic_tags = chronic_tags or []
    library = "medical" if goal == "medical" or chronic_tags else "fitness"
    lib = libs[library]
    templates = lib["templates"]
    # prefer age match
    candidates = [t for t in templates if t.get("age_group") == age_group]
    if not candidates:
        candidates = templates
    if library == "medical" and chronic_tags:
        tagged = [t for t in candidates if set(t.get("chronic_tags", [])) & set(chronic_tags)]
        if tagged:
            candidates = tagged
    tpl = candidates[0]
    exercises = resolve_exercises(lib, tpl.get("exercise_ids", []))
    payload = {
        "library": library,
        "template_id": tpl["id"],
        "mode": tpl.get("mode", ""),
        "intensity": tpl.get("intensity", ""),
        "frequency": tpl.get("frequency", ""),
        "duration": tpl.get("duration", ""),
        "cycle": tpl.get("cycle", ""),
        "volume": tpl.get("volume", ""),
        "progression": tpl.get("progression", ""),
        "exercises": exercises,
        "health_plan": {
            "medication": "",
            "psychology": "",
            "diet": "均衡饮食",
            "sleep": "保证7小时",
        },
    }
    return library, payload


def adjust_by_report(exercises: list[dict], score: float, errors: list[str]) -> tuple[list[dict], str]:
    new_ex = [dict(e) for e in exercises]
    note = ""
    if score < 70:
        for e in new_ex:
            e["sets"] = max(1, int(e.get("sets", 3)) - 1)
        note = "完成度偏低，下周组数-1；"
    if "knee_valgus_mild" in errors or "knee_valgus" in errors:
        new_ex.insert(
            0,
            {
                "id": "glute_activation",
                "name": "臀中肌激活（矫正）",
                "category": "矫正",
                "sets": 2,
                "reps": 12,
            },
        )
        note += "插入矫正激活动作；"
    return new_ex, note or "维持原处方，继续监督反馈。"
