/** Camera lifecycle owns its tracks, including permission/model requests still in flight. */
import { getPoseLandmarker, drawSkeleton } from "./usePoseLandmarker";

function angle(a, b, c) {
  const ab = { x: a.x - b.x, y: a.y - b.y };
  const cb = { x: c.x - b.x, y: c.y - b.y };
  const n1 = Math.hypot(ab.x, ab.y), n2 = Math.hypot(cb.x, cb.y);
  if (!n1 || !n2) return null;
  return Math.round(Math.acos(Math.min(1, Math.max(-1, (ab.x * cb.x + ab.y * cb.y) / (n1 * n2)))) * 180 / Math.PI);
}

export function createPoseCamera({ video, canvas, onHint, onFrame, onReady }) {
  let stream = null, raf = 0, generation = 0;
  let running = false, lastVideoTime = -1, landmarker = null;

  async function start() {
    stop();
    const attempt = generation;
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("此浏览器无法使用摄像头，请通过 HTTPS 打开并检查浏览器权限");
    }
    const acquired = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false,
    });
    if (attempt !== generation) {
      acquired.getTracks().forEach(track => track.stop());
      return false;
    }
    stream = acquired;
    try {
      video.src = "";
      video.srcObject = stream;
      await video.play();
      if (attempt !== generation) return false;
      onHint?.("摄像头已开启，正在加载姿态模型…");
      try {
        const model = await getPoseLandmarker();
        if (attempt !== generation) return false;
        landmarker = model;
        onReady?.(true);
        onHint?.("姿态模型就绪：请站入画面（镜像预览）");
      } catch (error) {
        if (attempt !== generation) return false;
        onHint?.("姿态模型加载失败，仅保留摄像头预览。请检查网络后关闭并重新打开摄像头。" + (error?.message || ""));
      }
      running = true;
      loop();
      return true;
    } catch (error) {
      if (attempt !== generation) return false;
      stop();
      throw error;
    }
  }

  function loop() {
    if (!running) return;
    const ctx = canvas.getContext("2d");
    const w = video.videoWidth || 640, h = video.videoHeight || 480;
    canvas.width = w;
    canvas.height = h;
    ctx.save();
    try {
      ctx.clearRect(0, 0, w, h);
      ctx.translate(w, 0);
      ctx.scale(-1, 1);
      ctx.drawImage(video, 0, 0, w, h);
      if (landmarker && video.currentTime !== lastVideoTime) {
        lastVideoTime = video.currentTime;
        const lm = landmarker.detectForVideo(video, performance.now())?.landmarks?.[0];
        if (lm) {
          onFrame?.(lm);
          if (!running) return;
          // The entire canvas is already mirrored, including the video.
          drawSkeleton(ctx, lm, w, h);
          const knee = angle(lm[23], lm[25], lm[27]) || angle(lm[24], lm[26], lm[28]);
          onHint?.(knee ? `膝角约 ${knee}° · ${knee < 70 ? "下蹲较深" : knee > 160 ? "接近站立" : "动作进行中"}` : "已检测到人体");
        } else {
          onHint?.("未检测到人体，请正对摄像头、全身入画");
        }
      }
    } catch {
      onHint?.("姿态识别暂时不可用，请检查画面，必要时重新打开摄像头");
    } finally {
      ctx.restore();
    }
    if (running) raf = requestAnimationFrame(loop);
  }

  function stop() {
    onReady?.(false);
    generation += 1;
    running = false;
    cancelAnimationFrame(raf);
    stream?.getTracks().forEach(track => track.stop());
    stream = null;
    landmarker = null;
    lastVideoTime = -1;
    video.srcObject = null;
  }

  return { start, stop };
}
