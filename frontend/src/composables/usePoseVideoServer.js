/** 离线视频：后端 RTMPose（rtmlib / OpenMMLab COCO-17） */
import api from "../api/client";
import { anglesFromCocoKeypoints, hintFromAngles } from "../utils/poseFormat";

/**
 * @param {object} opts
 * @param {string} [opts.videoPathRel] 如 data/demo_videos/squat/x.mp4 或 demo_videos/squat/x.mp4
 * @param {File} [opts.file] 无路径时上传
 * @param {number} [opts.sampleHz=6]
 * @param {string} [opts.exerciseId]
 * @param {number} [opts.sessionId] Current user's running training session for uploads.
 * @param {(p: {phase:string, progress:number, message?:string}) => void} [opts.onProgress]
 */
export async function processVideoServer({
  videoPathRel,
  file,
  sampleHz = 6,
  exerciseId,
  sessionId,
  onProgress,
  signal,
}) {
  let data;
  if (videoPathRel) {
    onProgress?.({ phase: "analysis", progress: 0.1, message: "正在分析视频动作…" });
    const { data: resp } = await api.post(
      "/pose/infer-video",
      { video_path: videoPathRel, sample_hz: sampleHz, exercise_id: exerciseId },
      { timeout: 600000, signal },
    );
    data = resp;
  } else if (file) {
    onProgress?.({ phase: "upload", progress: 0, message: "正在上传视频…" });
    const form = new FormData();
    const type = String(file.type || "").toLowerCase();
    const fallbackSuffix = type.includes("quicktime") ? "mov" : type.includes("webm") ? "webm" : "mp4";
    const uploadFile = String(file.name || "").trim()
      ? file
      : new File([file], `mobile-video-${Date.now()}.${fallbackSuffix}`, { type: file.type || "video/mp4" });
    form.append("file", uploadFile);
    form.append("sample_hz", String(sampleHz));
    if (exerciseId) form.append("exercise_id", exerciseId);
    if (sessionId) form.append("session_id", String(sessionId));
    const { data: resp } = await api.post("/pose/infer-video-upload", form, {
      timeout: 600000,
      signal,
      onUploadProgress: (event) => {
        if (event.total && event.loaded < event.total) {
          const ratio = Math.min(1, event.loaded / event.total);
          onProgress?.({
            phase: "upload",
            progress: ratio * 0.3,
            message: `正在上传视频 ${Math.round(ratio * 100)}%…`,
          });
        } else {
          onProgress?.({ phase: "analysis", progress: 0.35, message: "上传完成，正在分析视频动作…" });
        }
      },
    });
    data = resp;
  } else {
    throw new Error("缺少 videoPathRel 或 file");
  }

  const cocoFrames = data.coco17_frames || [];
  if (!cocoFrames.length) {
    throw new Error("视频中没有识别到完整人体，请调整拍摄角度后重试");
  }

  const meta = data.frame_meta || {};
  const last = cocoFrames[cocoFrames.length - 1];
  const hint = hintFromAngles(anglesFromCocoKeypoints(last.keypoints));

  onProgress?.({
    phase: "done",
    progress: 1,
    message: `${hint} · 视频动作分析完成`,
  });

  return {
    serverResult: data,
    cocoFrames,
    width: meta.width || 0,
    height: meta.height || 0,
    durationSec: meta.duration_sec || 0,
    hint,
    uploadRel: data.upload_rel,
  };
}
