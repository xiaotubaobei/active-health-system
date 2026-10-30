/** MediaPipe-33 ↔ COCO-17，见 docs/pose_session.md */
import { poseEstimatorMeta } from "../config/poseModel.js";

export const CONVERTER_VERSION = "mp33_to_coco17_v1";

/** COCO idx -> MediaPipe idx */
export const MP33_TO_COCO17 = [
  [0, 0],
  [1, 2],
  [2, 5],
  [3, 7],
  [4, 8],
  [5, 11],
  [6, 12],
  [7, 13],
  [8, 14],
  [9, 15],
  [10, 16],
  [11, 23],
  [12, 24],
  [13, 25],
  [14, 26],
  [15, 27],
  [16, 28],
];

export const MP33_NAMES = [
  "nose",
  "left_eye_inner",
  "left_eye",
  "left_eye_outer",
  "right_eye_inner",
  "right_eye",
  "right_eye_outer",
  "left_ear",
  "right_ear",
  "mouth_left",
  "mouth_right",
  "left_shoulder",
  "right_shoulder",
  "left_elbow",
  "right_elbow",
  "left_wrist",
  "right_wrist",
  "left_pinky",
  "right_pinky",
  "left_index",
  "right_index",
  "left_thumb",
  "right_thumb",
  "left_hip",
  "right_hip",
  "left_knee",
  "right_knee",
  "left_ankle",
  "right_ankle",
  "left_heel",
  "right_heel",
  "left_foot_index",
  "right_foot_index",
];

export function mpVisibilityToCocoV(visibility) {
  const v = visibility ?? 0;
  if (v < 0.5) return 0;
  if (v < 0.8) return 1;
  return 2;
}

export function landmarksToMp33Frame(landmarks, tMs, frameIndex) {
  const list = landmarks.map((p, i) => ({
    i,
    name: MP33_NAMES[i] || `joint_${i}`,
    x: p.x,
    y: p.y,
    z: p.z ?? 0,
    visibility: p.visibility ?? p.presence ?? 1,
  }));
  return { t_ms: Math.round(tMs), frame_index: frameIndex, landmarks: list };
}

export function mp33FrameToCoco17Keypoints(mpFrame) {
  const byIdx = {};
  for (const lm of mpFrame.landmarks || []) {
    byIdx[lm.i] = lm;
  }
  const keypoints = [];
  let num = 0;
  for (const [cocoIdx, mpIdx] of MP33_TO_COCO17) {
    const p = byIdx[mpIdx];
    if (!p) {
      keypoints.push(0, 0, 0);
      continue;
    }
    const v = mpVisibilityToCocoV(p.visibility);
    if (v > 0) num += 1;
    keypoints.push(p.x, p.y, v);
  }
  return {
    t_ms: mpFrame.t_ms,
    frame_index: mpFrame.frame_index,
    keypoints,
    num_keypoints: num,
  };
}

export function jointAngleDeg(a, b, c) {
  if (!a || !b || !c) return null;
  const ab = { x: a.x - b.x, y: a.y - b.y };
  const cb = { x: c.x - b.x, y: c.y - b.y };
  const dot = ab.x * cb.x + ab.y * cb.y;
  const n1 = Math.hypot(ab.x, ab.y);
  const n2 = Math.hypot(cb.x, cb.y);
  if (!n1 || !n2) return null;
  const cos = Math.min(1, Math.max(-1, dot / (n1 * n2)));
  return Math.round((Math.acos(cos) * 180) / Math.PI);
}

/** COCO-17 flat keypoints [x,y,v,...] normalized */
export function cocoFlatToPoints(flat) {
  const pts = [];
  for (let i = 0; i < 17; i++) {
    const v = flat[i * 3 + 2] ?? 0;
    if (v > 0) pts[i] = { x: flat[i * 3], y: flat[i * 3 + 1] };
    else pts[i] = null;
  }
  return pts;
}

const COCO17_BONES = [
  [0, 1],
  [0, 2],
  [1, 3],
  [2, 4],
  [5, 6],
  [5, 7],
  [7, 9],
  [6, 8],
  [8, 10],
  [5, 11],
  [6, 12],
  [11, 12],
  [11, 13],
  [13, 15],
  [12, 14],
  [14, 16],
];

/** 在 canvas 上绘制 COCO-17（flat 为归一化坐标） */
export function drawCoco17Skeleton(ctx, flat, w, h) {
  const pts = cocoFlatToPoints(flat);
  ctx.lineWidth = 3;
  ctx.strokeStyle = "#6eb5ff";
  ctx.fillStyle = "#fff";
  for (const [a, b] of COCO17_BONES) {
    const pa = pts[a];
    const pb = pts[b];
    if (!pa || !pb) continue;
    ctx.beginPath();
    ctx.moveTo(pa.x * w, pa.y * h);
    ctx.lineTo(pb.x * w, pb.y * h);
    ctx.stroke();
  }
  for (const p of pts) {
    if (!p) continue;
    ctx.beginPath();
    ctx.arc(p.x * w, p.y * h, 4, 0, Math.PI * 2);
    ctx.fill();
  }
}

export function anglesFromCocoKeypoints(flat) {
  const lm = cocoFlatToPoints(flat);
  const kneeL = jointAngleDeg(lm[11], lm[13], lm[15]);
  const kneeR = jointAngleDeg(lm[12], lm[14], lm[16]);
  const shoulderMid =
    lm[5] && lm[6] ? { x: (lm[5].x + lm[6].x) / 2, y: (lm[5].y + lm[6].y) / 2 } : null;
  const hipMid =
    lm[11] && lm[12] ? { x: (lm[11].x + lm[12].x) / 2, y: (lm[11].y + lm[12].y) / 2 } : null;
  let trunk = null;
  if (shoulderMid && hipMid) {
    const dx = shoulderMid.x - hipMid.x;
    const dy = shoulderMid.y - hipMid.y;
    trunk = Math.round(Math.abs((Math.atan2(dx, -dy) * 180) / Math.PI));
  }
  return { knee_flexion_l: kneeL, knee_flexion_r: kneeR, trunk_flexion_deg: trunk };
}

export function anglesFromLandmarks(landmarks) {
  const kneeL = jointAngleDeg(landmarks[23], landmarks[25], landmarks[27]);
  const kneeR = jointAngleDeg(landmarks[24], landmarks[26], landmarks[28]);
  const shoulderMid = landmarks[11] && landmarks[12]
    ? { x: (landmarks[11].x + landmarks[12].x) / 2, y: (landmarks[11].y + landmarks[12].y) / 2 }
    : null;
  const hipMid = landmarks[23] && landmarks[24]
    ? { x: (landmarks[23].x + landmarks[24].x) / 2, y: (landmarks[23].y + landmarks[24].y) / 2 }
    : null;
  let trunk = null;
  if (shoulderMid && hipMid) {
    const dx = shoulderMid.x - hipMid.x;
    const dy = shoulderMid.y - hipMid.y;
    trunk = Math.round(Math.abs((Math.atan2(dx, -dy) * 180) / Math.PI));
  }
  return { knee_flexion_l: kneeL, knee_flexion_r: kneeR, trunk_flexion_deg: trunk };
}

function summarizeAngles(perFrame) {
  const pick = (key) => {
    const vals = perFrame.map((f) => f[key]).filter((v) => v != null);
    if (!vals.length) return null;
    return {
      min: Math.min(...vals),
      max: Math.max(...vals),
      mean: Math.round(vals.reduce((a, b) => a + b, 0) / vals.length),
    };
  };
  return {
    knee_flexion_l: pick("knee_flexion_l"),
    knee_flexion_r: pick("knee_flexion_r"),
    trunk_flexion_deg: pick("trunk_flexion_deg"),
  };
}

export function hintFromAngles(ang) {
  const knee = ang.knee_flexion_l || ang.knee_flexion_r;
  if (knee == null) return "未检测到稳定下肢关键点";
  if (knee < 70) return `膝角约 ${knee}° · 下蹲较深`;
  if (knee > 160) return `膝角约 ${knee}° · 接近站立`;
  return `膝角约 ${knee}° · 动作进行中`;
}

export function buildPoseSummary({
  sessionId,
  exerciseId,
  exerciseName,
  mpFrames,
  source,
  videoFileName = "",
  width = 0,
  height = 0,
}) {
  const cocoFrames = mpFrames.map(mp33FrameToCoco17Keypoints);
  const perFrame = mpFrames.map((f) => {
    const lm = {};
    for (const p of f.landmarks || []) lm[p.i] = p;
    const raw = Array.from({ length: 33 }, (_, i) => lm[i] || { x: 0, y: 0, visibility: 0 });
    const a = anglesFromLandmarks(raw);
    return { t_ms: f.t_ms, ...a };
  });
  const summary = summarizeAngles(perFrame);
  const lastAng = perFrame[perFrame.length - 1] || {};

  return {
    schema_version: "1.0.0",
    session_id: sessionId ?? null,
    exercise_id: exerciseId,
    exercise_name: exerciseName,
    canonical_format: "coco17",
    capture_format: "mediapipe33",
    converter_version: CONVERTER_VERSION,
    estimator: {
      ...poseEstimatorMeta(),
      runtime: source === "offline_video" ? "browser_video_file" : "browser",
      fps_sample: mpFrames.length > 1
        ? Math.round(
            (mpFrames.length / Math.max(1, (mpFrames[mpFrames.length - 1].t_ms - mpFrames[0].t_ms) / 1000)) *
              10
          ) / 10
        : 0,
    },
    refiner: { name: "none", mode: "raw_only" },
    frame_meta: {
      width,
      height,
      coord_space: "normalized_0_1",
      video_file: videoFileName || undefined,
    },
    sequences: {
      mediapipe33: { frames: mpFrames },
      coco17: { frames: cocoFrames },
    },
    angles: { per_frame: perFrame, summary },
    hints: [
      {
        code: "pose_live",
        severity: "info",
        message: hintFromAngles(lastAng),
        t_ms: perFrame[perFrame.length - 1]?.t_ms ?? 0,
      },
    ],
    raw: { format: "coco17", frame_count: cocoFrames.length },
    optimized: { format: "coco17", frame_count: cocoFrames.length, refiner: "none" },
    source,
  };
}

/** 服务端 RTMPose 直出 COCO-17（无 MP33 原始序列） */
export function buildPoseSummaryFromServer({
  sessionId,
  exerciseId,
  exerciseName,
  serverResult,
  source = "offline_video",
  videoFileName = "",
}) {
  const cocoFrames = serverResult.coco17_frames || [];
  const meta = serverResult.frame_meta || {};
  const estimator = serverResult.estimator || { name: "rtmpose_balanced", family: "rtmpose_mmpose" };
  const perFrame = cocoFrames.map((f) => ({
    t_ms: f.t_ms,
    ...anglesFromCocoKeypoints(f.keypoints),
  }));
  const summary = summarizeAngles(perFrame);
  const lastAng = perFrame[perFrame.length - 1] || {};

  return {
    schema_version: "1.0.0",
    session_id: sessionId ?? null,
    exercise_id: exerciseId,
    exercise_name: exerciseName,
    canonical_format: "coco17",
    capture_format: "coco17",
    converter_version: "rtmpose_direct_v1",
    estimator: {
      ...estimator,
      runtime: "server_rtmpose",
      fps_sample: serverResult.sample_hz ?? 6,
    },
    refiner: { name: "none", mode: "raw_only" },
    frame_meta: {
      width: meta.width || 0,
      height: meta.height || 0,
      coord_space: "normalized_0_1",
      video_file: videoFileName || meta.source_file,
    },
    sequences: {
      mediapipe33: { frames: [] },
      coco17: { frames: cocoFrames },
    },
    angles: { per_frame: perFrame, summary },
    hints: [
      {
        code: "pose_rtmpose",
        severity: "info",
        message: hintFromAngles(lastAng),
        t_ms: perFrame[perFrame.length - 1]?.t_ms ?? 0,
      },
    ],
    raw: { format: "coco17", frame_count: cocoFrames.length },
    optimized: { format: "coco17", frame_count: cocoFrames.length, refiner: "none" },
    source,
  };
}
