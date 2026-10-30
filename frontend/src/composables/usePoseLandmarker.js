/** 共享 MediaPipe PoseLandmarker（摄像头 / 离线视频） */
import { POSE_LANDMARKER_VARIANT, POSE_MODEL_URL } from "../config/poseModel.js";

const WASM = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm";

let landmarkerPromise = null;

async function createLandmarker(delegate) {
  const { FilesetResolver, PoseLandmarker } = await import("@mediapipe/tasks-vision");
  const vision = await FilesetResolver.forVisionTasks(WASM);
  return PoseLandmarker.createFromOptions(vision, {
    baseOptions: { modelAssetPath: POSE_MODEL_URL, delegate },
    runningMode: "VIDEO",
    numPoses: 1,
  });
}

export { POSE_LANDMARKER_VARIANT };

export async function getPoseLandmarker() {
  if (!landmarkerPromise) {
    landmarkerPromise = (async () => {
      try {
        return await createLandmarker("GPU");
      } catch {
        return await createLandmarker("CPU");
      }
    })();
  }
  return landmarkerPromise;
}

export { jointAngleDeg as angleFromLandmarks } from "../utils/poseFormat.js";

export function drawSkeleton(ctx, lm, w, h, mirror = false) {
  const pts = mirror ? lm.map((p) => ({ ...p, x: 1 - p.x })) : lm;
  const pairs = [
    [11, 12],
    [11, 13],
    [13, 15],
    [12, 14],
    [14, 16],
    [11, 23],
    [12, 24],
    [23, 24],
    [23, 25],
    [25, 27],
    [24, 26],
    [26, 28],
  ];
  ctx.lineWidth = 3;
  ctx.strokeStyle = "#5ee0b0";
  ctx.fillStyle = "#fff";
  for (const [a, b] of pairs) {
    if (!pts[a] || !pts[b]) continue;
    ctx.beginPath();
    ctx.moveTo(pts[a].x * w, pts[a].y * h);
    ctx.lineTo(pts[b].x * w, pts[b].y * h);
    ctx.stroke();
  }
  for (const p of pts) {
    if (!p) continue;
    ctx.beginPath();
    ctx.arc(p.x * w, p.y * h, 4, 0, Math.PI * 2);
    ctx.fill();
  }
}
