"""Validate manually entered scale scores before saving an assessment."""
from math import isfinite

from fastapi import HTTPException

from .catalog import load_fitness_scales
from ..models.entities import FitnessAssessment, FitnessBaseline


def evaluate_scores(scale_id: str, scores: dict[str, float]) -> tuple[dict, float, str]:
    scale = next((s for s in load_fitness_scales() if s["id"] == scale_id), None)
    if scale is None:
        raise HTTPException(422, "请选择有效的体适能量表")
    expected = {item["key"] for item in scale["items"]}
    if set(scores) - expected:
        raise HTTPException(422, "分数包含当前量表以外的项目")
    for item in scale["items"]:
        value = scores.get(item["key"])
        if value is None or not isfinite(value) or not 0 <= value <= item.get("max_score", 100):
            raise HTTPException(422, f"请填写「{item['name']}」的有效分数（0–100）")
    weights = sum(float(item["weight"]) for item in scale["items"])
    total = round(sum(scores[item["key"]] * float(item["weight"]) for item in scale["items"]) / weights, 2)
    level = "excellent" if total >= 85 else "good" if total >= 70 else "average" if total >= 55 else "poor"
    return scale, total, level


def require_age_scale(age_group: str, scale_id: str):
    if scale_id != ("youth" if age_group == "youth" else "middle_elder"):
        raise HTTPException(422, "量表与档案年龄组不匹配，请核对档案或选择对应量表")


def save_assessment(db, user, scale, scores, total_score, level, pose_baseline=None):
    """调用者持有用户锁；首次实际录入才建基线，后续录入不覆盖。"""
    assessment = FitnessAssessment(user_id=user.id, scale_id=scale["id"], scores=scores,
                                   total_score=total_score, level=level)
    db.add(assessment)
    db.flush()
    baseline = db.query(FitnessBaseline).filter_by(user_id=user.id).first()
    if baseline is None:
        baseline = FitnessBaseline(
            user_id=user.id, assessment_id=assessment.id, scores=scores,
            total_score=total_score, level=level, pose_baseline=pose_baseline or {},
            profile_snapshot={key: getattr(user, key) for key in
                              ("age_group", "height_cm", "weight_kg", "goal", "chronic_tags")},
        )
        db.add(baseline)
    return assessment, baseline
