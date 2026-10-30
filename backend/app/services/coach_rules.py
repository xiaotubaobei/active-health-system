"""运动中实时规则引擎 v1：阈值限制同提示 ≥3s 不重复。"""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class CoachState:
    last_by_code: dict[str, float] = field(default_factory=dict)
    min_interval_s: float = 3.0

    def allow(self, code: str, now: float | None = None) -> bool:
        now = now if now is not None else time.time()
        last = self.last_by_code.get(code, 0.0)
        if now - last < self.min_interval_s:
            return False
        self.last_by_code[code] = now
        return True


# session_id -> CoachState
_STATES: dict[int, CoachState] = {}


def get_state(session_id: int) -> CoachState:
    if session_id not in _STATES:
        _STATES[session_id] = CoachState()
    return _STATES[session_id]


def clear_state(session_id: int) -> None:
    _STATES.pop(session_id, None)


def evaluate_tick(
    session_id: int,
    *,
    exercise_id: str = "squat",
    knee_l: float | None = None,
    knee_r: float | None = None,
    trunk_lean: float | None = None,
) -> dict | None:
    """根据姿态指标返回一条 coach_hint，或 None（无需提示）。"""
    state = get_state(session_id)
    knee = None
    for v in (knee_l, knee_r):
        if v is not None:
            knee = v if knee is None else min(knee, v)

    eid = (exercise_id or "squat").lower()

    # 深蹲类：膝角过大=未蹲够；过小=过深；躯干前倾过大
    if eid in ("squat", "bodyweight_squat", "goblet_squat") or "squat" in eid:
        if knee is not None and knee > 140:
            code = "squat_shallow"
            if state.allow(code):
                return {
                    "type": "coach_hint",
                    "level": "warn",
                    "code": code,
                    "text": "再蹲深一点，髋膝继续下沉",
                }
        if knee is not None and knee < 55:
            code = "squat_too_deep"
            if state.allow(code):
                return {
                    "type": "coach_hint",
                    "level": "info",
                    "code": code,
                    "text": "下蹲已够深，注意控制起身节奏",
                }
        if trunk_lean is not None and trunk_lean > 35:
            code = "trunk_lean"
            if state.allow(code):
                return {
                    "type": "coach_hint",
                    "level": "warn",
                    "code": code,
                    "text": "躯干前倾偏大，尝试挺胸、重心后移",
                }

    if eid in ("push_up", "pushup") or "push" in eid:
        if trunk_lean is not None and trunk_lean > 25:
            code = "pushup_hip_sag"
            if state.allow(code):
                return {
                    "type": "coach_hint",
                    "level": "warn",
                    "code": code,
                    "text": "保持躯干一条直线，收紧核心",
                }

    if knee is not None and 70 <= knee <= 120:
        code = "good_range"
        if state.allow(code):
            return {
                "type": "coach_hint",
                "level": "info",
                "code": code,
                "text": "角度不错，保持节奏",
            }
    return None
