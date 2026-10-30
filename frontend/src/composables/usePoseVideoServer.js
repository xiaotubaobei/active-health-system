/** 离线视频：后端 RTMPose（rtmlib / OpenMMLab COCO-17） */
import api from "../api/client";
import { anglesFromCocoKeypoints, hintFromAngles } from "../utils/poseFormat";

/**
 * @param {object} opts
 * @param {string} [opts.videoPathRel] 如 data/demo_videos/squat/x.mp4 或 demo_videos/squat/x.mp4
 * @param {File} [opts.file] 无路径时上传
 * @param {number} [opts.sampleHz=6]
 * @param {string} [opts.exerciseId]
 * @param {(p: {phase:string, progress:number, message?:string}) => void} [opts.onProgress]
 */
export async function processVideoServer({
  videoPathRel,
  file,
  sampleHz = 6,
  exerciseId,
  onProgress,
}) {
  onProgress?.({ phase: "scan", progress: 0.05, message: "服务端 RTMPose 解析中（首次可能下载权重）…" });

  let data;
  if (videoPathRel) {
    const { data: resp } = await api.post(
      "/pose/infer-video",
      { video_path: videoPathRel, sample_hz: sampleHz, exercise_id: exerciseId },
      { timeout: 600000 },
    );
    data = resp;
  } else if (file) {
    const form = new FormData();
    form.append("file", file);
    form.append("sample_hz", String(sampleHz));
    if (exerciseId) form.append("exercise_id", exerciseId);
    const { data: resp } = await api.post("/pose/infer-video-upload", form, {
      timeout: 600000,
      headers: { "Content-Type": "multipart/form-data" },
    });
    data = resp;
  } else {
    throw new Error("缺少 videoPathRel 或 file");
  }

  const cocoFrames = data.coco17_frames || [];
  if (!cocoFrames.length) {
    throw new Error("RTMPose 未检测到人体关键点");
  }

  const meta = data.frame_meta || {};
  const last = cocoFrames[cocoFrames.length - 1];
  const hint = hintFromAngles(anglesFromCocoKeypoints(last.keypoints));

  onProgress?.({
    phase: "done",
    progress: 1,
    message: `${hint} · RTMPose ${cocoFrames.length} 帧`,
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
