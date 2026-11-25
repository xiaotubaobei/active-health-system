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


class NoMatchingTemplate(ValueError):
    """目录未覆盖当前资料；不能用其他人群的模板代替。"""


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
    candidates = [t for t in templates if t.get("age_group") == age_group]
    if not candidates:
        raise NoMatchingTemplate("现有模板没有覆盖你所选的年龄组，请联系项目专业人员评估。")
    if library == "medical":
        if not chronic_tags:
            raise NoMatchingTemplate("健康管理目标尚无已确认的适用情况，暂不生成模板。请联系项目专业人员评估，不要为了匹配模板猜填健康标签。")
        # 当前目录只有标签，没有合并病种的适配规则；单个标签重合不代表覆盖全部情况。
        candidates = [t for t in candidates if set(t.get("chronic_tags", [])) == set(chronic_tags)]
    else:
        candidates = [t for t in candidates if t.get("goal") == goal]
    if len(candidates) != 1:
        raise NoMatchingTemplate("现有模板无法唯一、完整地匹配你填写的目标和健康标签，暂不生成方案。请联系项目专业人员评估；标签匹配也不代表已经确认适合训练。")
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
            "diet": "",
            "sleep": "",
        },
    }
    return library, payload


def template_availability(age_group: str, goal: str, chronic_tags: list | None = None) -> dict:
    try:
        library, payload = pick_template(age_group, goal, chronic_tags)
    except NoMatchingTemplate as error:
        return {"matched": False, "reason": str(error), "library": None, "template_id": None}
    return {"matched": True, "library": library, "template_id": payload["template_id"],
            "reason": "目录中有年龄组及标签匹配的模板，仅供查看和送审，尚未按个人测评或活动限制制定运动量。"}


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
