"""RTMPose via rtmlib (OpenMMLab ONNX + OpenCV DNN，COCO-17)。"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

# lightweight | balanced | performance  → RTMPose-S / M / L 档
RTM_MODE = os.getenv("RTMPOSE_MODE", "balanced").lower()
RTM_DEVICE = os.getenv("RTMPOSE_DEVICE", "cpu").lower()


def _default_backend() -> str:
    explicit = os.getenv("RTMPOSE_BACKEND", "").strip().lower()
    if explicit:
        return explicit
    try:
        import onnxruntime  # noqa: F401

        return "onnxruntime"
    except Exception:
        return "opencv"


RTM_BACKEND = _default_backend()


@lru_cache(maxsize=1)
def _body():
    from rtmlib import Body

    mode = RTM_MODE if RTM_MODE in ("lightweight", "balanced", "performance") else "balanced"
    backend = _default_backend()
    return Body(mode=mode, backend=backend, device=RTM_DEVICE)


def estimator_name() -> str:
    mode = RTM_MODE if RTM_MODE in ("lightweight", "balanced", "performance") else "balanced"
    return f"rtmpose_{mode}"


def _coco_keypoints_norm(kpts: np.ndarray, scores: np.ndarray, w: int, h: int) -> list[float]:
    """COCO-17 flat [x,y,v,...] normalized."""
    out: list[float] = []
    for i in range(17):
        x, y = float(kpts[i, 0]), float(kpts[i, 1])
        sc = float(scores[i]) if scores is not None and i < len(scores) else 1.0
        v = 2 if sc >= 0.35 else (1 if sc >= 0.15 else 0)
        out.extend([x / w, y / h, v])
    return out


def process_video(path: Path, sample_hz: float = 6.0) -> dict:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(str(path))

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频: {path.name}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    duration = frame_count / fps if frame_count > 0 else 0.0

    body = _body()
    interval = max(1.0 / sample_hz, 0.05)
    t = 0.0
    coco_frames: list[dict] = []
    frame_index = 0

    while t <= duration + 0.001:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ok, frame = cap.read()
        if not ok or frame is None:
            t += interval
            continue

        fh, fw = frame.shape[:2]
        keypoints, scores = body(frame)
        if keypoints is None or len(keypoints) == 0:
            t += interval
            continue

        kpts = np.asarray(keypoints[0])
        sc = np.asarray(scores[0]) if scores is not None else np.ones(17)
        flat = _coco_keypoints_norm(kpts, sc, fw, fh)
        num = sum(1 for i in range(17) if flat[i * 3 + 2] > 0)
        coco_frames.append(
            {
                "t_ms": int(round(t * 1000)),
                "frame_index": frame_index,
                "keypoints": flat,
                "num_keypoints": num,
            }
        )
        frame_index += 1
        t += interval

    cap.release()

    if not coco_frames:
        raise RuntimeError("视频中未检测到人体（RTMPose）")

    return {
        "mode": "rtmpose",
        "estimator": {
            "name": estimator_name(),
            "family": "rtmpose_mmpose",
            "runtime": "server_rtmlib",
            "backend": _default_backend(),
            "rtm_mode": RTM_MODE,
        },
        "frame_meta": {
            "width": w,
            "height": h,
            "coord_space": "normalized_0_1",
            "duration_sec": round(duration, 3),
            "source_file": path.name,
        },
        "sample_hz": sample_hz,
        "coco17_frames": coco_frames,
    }
