/** 离线视频：按间隔抽帧 → MediaPipe → MP33 + COCO 序列 */
import { getPoseLandmarker, drawSkeleton } from "./usePoseLandmarker";
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
 * @param {number} [opts.sampleHz=6]
 * @param {(p: {phase:string, progress:number, message?:string}) => void} [opts.onProgress]
 */
export async function processVideoFile({ video, canvas, file, sampleHz = 6, onProgress }) {
  const url = URL.createObjectURL(file);
  video.srcObject = null;
  video.src = url;
  video.muted = true;
  video.playsInline = true;

  await new Promise((resolve, reject) => {
    video.onloadedmetadata = () => resolve();
    video.onerror = () => reject(new Error("无法读取视频文件"));
  });

  const duration = video.duration;
  if (!duration || !Number.isFinite(duration)) {
    URL.revokeObjectURL(url);
    throw new Error("视频时长无效");
  }

  const landmarker = await getPoseLandmarker();
  const intervalSec = 1 / sampleHz;
  const mpFrames = [];
  const w = video.videoWidth;
  const h = video.videoHeight;
  const ctx = canvas?.getContext("2d");

  let t = 0;
  let frameIndex = 0;
  while (t <= duration + 0.001) {
    video.currentTime = Math.min(t, duration);
    await new Promise((resolve) => {
      const onSeeked = () => {
        video.removeEventListener("seeked", onSeeked);
        resolve();
      };
      video.addEventListener("seeked", onSeeked);
    });

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

  URL.revokeObjectURL(url);
  video.removeAttribute("src");
  video.load();

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
}
