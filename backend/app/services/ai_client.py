import httpx
from ..config import AI_ENDPOINTS


async def _post(service: str, path: str, payload: dict, fallback: dict) -> dict:
    base = AI_ENDPOINTS.get(service)
    if not base:
        return {**fallback, "mode": "local_fallback"}
    url = f"{base.rstrip('/')}{path}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            data.setdefault("mode", "remote")
            return data
    except Exception as e:
        return {**fallback, "mode": "local_fallback", "error": str(e)}


async def pose_infer(payload: dict) -> dict:
    return await _post(
        "pose",
        "/infer",
        payload,
        {"keypoints": [], "angles": {}, "hints": ["offline mock pose"]},
    )


async def pose_infer_video(payload: dict) -> dict:
    base = AI_ENDPOINTS.get("pose")
    if not base:
        return {"mode": "local_fallback", "error": "AI_POSE_URL 未配置"}
    url = f"{base.rstrip('/')}/infer/video"
    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            data.setdefault("mode", "rtmpose")
            return data
    except Exception as e:
        return {"mode": "local_fallback", "error": str(e)}


async def pose_estimator_info() -> dict:
    base = AI_ENDPOINTS.get("pose")
    if not base:
        return {"mode": "local_fallback"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{base.rstrip('/')}/estimator")
            r.raise_for_status()
            return r.json()
    except Exception as e:
        return {"mode": "local_fallback", "error": str(e)}


async def parsing_analyze(payload: dict) -> dict:
    return await _post(
        "parsing",
        "/analyze",
        payload,
        {"parts": ["torso"], "ratios": {"torso": 0.3}, "open_set": True},
    )


async def behavior_all(payload: dict) -> dict:
    return await _post(
        "behavior",
        "/infer_all",
        payload,
        {
            "tasks": {
                "recognize": {"class": payload.get("exercise_name", "unknown")},
                "localize": {"segments": []},
                "segment": {"mask_timeline": []},
                "assess": {"score": 75.0, "errors": []},
                "describe": {"description": "offline mock description"},
            }
        },
    )


async def video_cot_evaluate(payload: dict) -> dict:
    name = payload.get("exercise_name") or "动作"
    return await _post(
        "video_cot",
        "/evaluate",
        payload,
        {
            "steps": [f"mock step for {name}"],
            "score": 75.0,
            "errors": [],
            "advice": "offline mock advice",
            "raw_cot": "offline",
        },
    )
