"""个人运动知识库：写入与摘要。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models.entities import BehaviorReport, CoachEvent, ExerciseSession, KbEntry, Prescription


def pose_digest(pose_summary: dict | None) -> dict:
    p = pose_summary or {}
    frames = (
        (p.get("sequences") or {}).get("coco17", {}).get("frames")
        or (p.get("raw") or {}).get("frame_count")
        or []
    )
    n = len(frames) if isinstance(frames, list) else int(frames or 0)
    estimator = (p.get("estimator") or {}) if isinstance(p.get("estimator"), dict) else {}
    return {
        "frame_count": n,
        "estimator": estimator.get("name") or estimator.get("family") or p.get("source") or "",
        "source": p.get("source") or "",
        "schema_version": p.get("schema_version") or "",
    }


def coach_digest(db: Session, session_id: int) -> dict:
    rows = (
        db.query(CoachEvent)
        .filter(CoachEvent.session_id == session_id)
        .order_by(CoachEvent.id.asc())
        .all()
    )
    by_code: dict[str, int] = {}
    for r in rows:
        by_code[r.code] = by_code.get(r.code, 0) + 1
    return {
        "count": len(rows),
        "by_code": by_code,
        "levels": {
            "info": sum(1 for r in rows if r.level == "info"),
            "warn": sum(1 for r in rows if r.level == "warn"),
        },
    }


def history_compare_note(db: Session, user_id: int, score: float, exercise_id: str) -> str:
    prev = (
        db.query(KbEntry)
        .filter(KbEntry.user_id == user_id, KbEntry.exercise_id == exercise_id)
        .order_by(KbEntry.id.desc())
        .first()
    )
    if not prev:
        return "首次完成该动作，已写入个人运动档案。"
    diff = round(float(score) - float(prev.score or 0), 1)
    if diff > 2:
        return f"相对上次（{prev.score} 分）提升约 {diff} 分，动作更稳。"
    if diff < -2:
        return f"相对上次（{prev.score} 分）低约 {abs(diff)} 分，建议对照上次错误点复盘。"
    return f"与上次（{prev.score} 分）接近，保持当前处方节奏即可。"


def append_kb_entry(
    db: Session,
    *,
    session: ExerciseSession,
    report: BehaviorReport,
    new_presc: Prescription | None,
) -> KbEntry:
    cot = report.cot or {}
    vu = report.video_understanding or cot
    score = float(vu.get("score") or cot.get("score") or 0)
    errors = list(vu.get("errors") or cot.get("errors") or [])
    advice = str(vu.get("advice") or cot.get("advice") or "")
    note = history_compare_note(db, session.user_id, score, session.exercise_id)

    presc_ver = 0
    if session.prescription_id:
        p = db.get(Prescription, session.prescription_id)
        if p:
            presc_ver = p.version
    if new_presc:
        presc_ver = new_presc.version

    entry = KbEntry(
        user_id=session.user_id,
        session_id=session.id,
        prescription_id=new_presc.id if new_presc else (session.prescription_id or 0),
        prescription_version=presc_ver,
        exercise_id=session.exercise_id,
        exercise_name=session.exercise_name,
        pose_digest=pose_digest(session.pose_summary),
        coach_digest=coach_digest(db, session.id),
        multimodal={
            "score": score,
            "errors": errors,
            "advice": advice,
            "steps": (vu.get("steps") or cot.get("steps") or [])[:8],
            "mode": vu.get("mode") or cot.get("mode") or "",
        },
        score=score,
        errors=errors,
        advice=advice,
        history_note=note,
        prescription_changed=bool(new_presc),
    )
    db.add(entry)
    return entry


def kb_summary(db: Session, user_id: int, limit: int = 20) -> dict:
    entries = (
        db.query(KbEntry)
        .filter(KbEntry.user_id == user_id)
        .order_by(KbEntry.id.desc())
        .limit(limit)
        .all()
    )
    sessions_n = (
        db.query(ExerciseSession)
        .filter(ExerciseSession.user_id == user_id, ExerciseSession.status == "finished")
        .count()
    )
    scores = [float(e.score) for e in entries if e.score is not None]
    recent_errors: dict[str, int] = {}
    for e in entries[:10]:
        for err in e.errors or []:
            recent_errors[str(err)] = recent_errors.get(str(err), 0) + 1
    last_notes = [e.history_note for e in entries[:5] if e.history_note]
    return {
        "user_id": user_id,
        "finished_sessions": sessions_n,
        "kb_entries": len(entries),
        "avg_score_recent": round(sum(scores) / len(scores), 1) if scores else None,
        "recent_errors": recent_errors,
        "last_notes": last_notes,
        "entries": [
            {
                "id": e.id,
                "session_id": e.session_id,
                "exercise_id": e.exercise_id,
                "exercise_name": e.exercise_name,
                "score": e.score,
                "errors": e.errors,
                "history_note": e.history_note,
                "prescription_version": e.prescription_version,
                "prescription_changed": e.prescription_changed,
                "coach_digest": e.coach_digest,
                "pose_digest": e.pose_digest,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ],
    }
