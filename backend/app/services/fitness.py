"""Validate manually entered scale scores before saving an assessment."""
from math import isfinite

from fastapi import HTTPException

from .catalog import load_fitness_scales


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
