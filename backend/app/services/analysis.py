"""Keep demonstration/fallback scores separate from model assessments."""
from math import isfinite


def analysis_summary(result: dict | None) -> dict:
    result = result or {}
    mode = result.get("mode") or "unknown"
    score = result.get("score")
    valid_score = isinstance(score, (int, float)) and not isinstance(score, bool) and isfinite(score) and 0 <= score <= 100
    is_model = mode in ("remote", "model") and valid_score and not result.get("error") and result.get("status") not in ("failed", "error")
    status = "model" if is_model else "demo" if mode in ("mock", "local_fallback") else "unavailable"
    return {
        "status": status,
        "mode": mode,
        "score": float(score) if is_model else None,
        "message": "模型评估结果，处方保留待审核" if is_model else "当前为演示或未完成评估，不计入成绩，也不自动调整处方",
    }
