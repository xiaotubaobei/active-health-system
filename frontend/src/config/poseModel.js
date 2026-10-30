/**
 * 浏览器端姿态估计：MediaPipe Pose Landmarker（Google Tasks Vision）
 * 可选 lite | full | heavy — 默认 full（精度/速度平衡）
 *
 * 构建时覆盖：VITE_POSE_LANDMARKER=heavy npm run dev
 */
const VARIANT = (import.meta.env.VITE_POSE_LANDMARKER || "full").toLowerCase();

const MODEL_BASE =
  "https://storage.googleapis.com/mediapipe-models/pose_landmarker";

export const POSE_LANDMARKER_VARIANT = ["lite", "full", "heavy"].includes(VARIANT)
  ? VARIANT
  : "full";

export const POSE_MODEL_URL =
  `${MODEL_BASE}/pose_landmarker_${POSE_LANDMARKER_VARIANT}/float16/1/` +
  `pose_landmarker_${POSE_LANDMARKER_VARIANT}.task`;

export function poseEstimatorMeta() {
  return {
    name: `mediapipe_pose_landmarker_${POSE_LANDMARKER_VARIANT}`,
    family: "mediapipe_pose_landmarker",
    variant: POSE_LANDMARKER_VARIANT,
    model_url: POSE_MODEL_URL,
  };
}

/** 离线视频：server=RTMPose(COCO17) | browser=MediaPipe */
export const POSE_OFFLINE_ESTIMATOR = (
  import.meta.env.VITE_POSE_OFFLINE || "server"
).toLowerCase();

export function isOfflineRtmpose() {
  return POSE_OFFLINE_ESTIMATOR === "server" || POSE_OFFLINE_ESTIMATOR === "rtmpose";
}
