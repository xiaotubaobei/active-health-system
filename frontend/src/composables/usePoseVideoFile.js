/** 离线视频：按间隔抽帧 → MediaPipe → MP33 + COCO 序列 */
import { getPoseLandmarker, drawSkeleton } from "./usePoseLandmarker";
import { validateVideoFile, MAX_VIDEO_SECONDS, checkAborted, abortable, loadVideoSource, seekVideo } from '../utils/videoInput.js';
import {
  landmarksToMp33Frame,
  anglesFromLandmarks,
  hintFromAngles,
} from "../utils/poseFormat";

/**
 * @param {object} opts
 * @param {HTMLVideoElement} opts.video
 * @param {HTMLCanvasElement} [opts.canvas]
 * @param {File} opts.file
 * @param {AbortSignal} [opts.signal]
 * @param {number} [opts.sampleHz=6]
 * @param {(p: {phase:string, progress:number, message?:string}) => void} [opts.onProgress]
 */
export async function processVideoFile({ video, canvas, file, sampleHz = 6, onProgress, signal }) {
  validateVideoFile(file);
  checkAborted(signal);
  if (!Number.isFinite(sampleHz) || sampleHz <= 0 || sampleHz > 6) throw new Error('视频采样率须在0到6之间');
  const url = URL.createObjectURL(file);
  try {
    video.muted = true;
    video.playsInline = true;
    onProgress?.({ phase: 'load', progress: 0, message: '正在读取视频…' });
    await loadVideoSource(video, url, { signal });

    const duration = video.duration;
    if (!duration || !Number.isFinite(duration)) {
      throw new Error("视频时长无效");
    }
    if (duration > MAX_VIDEO_SECONDS) throw new Error('视频不能超过3分钟，请先截取要检查的动作片段');

    onProgress?.({ phase: 'model', progress: 0, message: '正在准备姿态模型，可随时取消…' });
    const landmarker = await abortable(getPoseLandmarker(), signal);
    const intervalSec = 1 / sampleHz;
    const mpFrames = [];
    const w = video.videoWidth;
    const h = video.videoHeight;
    const ctx = canvas?.getContext("2d");

    let t = 0;
    let frameIndex = 0;
    while (t < duration) {
      checkAborted(signal);
      await seekVideo(video, t, { signal });
      checkAborted(signal);

      const res = landmarker.detectForVideo(video, performance.now());
      const lm = res?.landmarks?.[0];
      if (lm) {
        mpFrames.push(landmarksToMp33Frame(lm, t * 1000, frameIndex));
        frameIndex += 1;
        if (ctx && canvas) {
          canvas.width = w;
          canvas.height = h;
          ctx.clearRect(0, 0, w, h);
          ctx.drawImage(video, 0, 0, w, h);
          drawSkeleton(ctx, lm, w, h, false);
        }
      }

      onProgress?.({
        phase: "scan",
        progress: Math.min(1, t / duration),
        message: `解析 ${Math.round(t)}s / ${Math.round(duration)}s · 已采 ${mpFrames.length} 帧`,
      });
      t += intervalSec;
    }

    if (!mpFrames.length) {
      throw new Error("视频中未检测到人体，请换侧面/正面全身更清晰的片段");
    }

    const lastLm = mpFrames[mpFrames.length - 1].landmarks;
    const byIdx = {};
    for (const p of lastLm) byIdx[p.i] = p;
    const raw = Array.from({ length: 33 }, (_, i) => byIdx[i] || { x: 0, y: 0, visibility: 0 });
    const hint = hintFromAngles(anglesFromLandmarks(raw));

    onProgress?.({ phase: "done", progress: 1, message: hint });

    return { mpFrames, width: w, height: h, durationSec: duration, hint };
  } finally {
    URL.revokeObjectURL(url);
    video.pause();
    video.removeAttribute('src');
    video.load();
  }
}
