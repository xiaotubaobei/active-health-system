/** 浏览器摄像头 + MediaPipe Pose 骨架叠加（演示用）。 */

import { getPoseLandmarker, drawSkeleton } from "./usePoseLandmarker";



function angle(a, b, c) {

  const ab = { x: a.x - b.x, y: a.y - b.y };

  const cb = { x: c.x - b.x, y: c.y - b.y };

  const dot = ab.x * cb.x + ab.y * cb.y;

  const n1 = Math.hypot(ab.x, ab.y);

  const n2 = Math.hypot(cb.x, cb.y);

  if (!n1 || !n2) return null;

  const cos = Math.min(1, Math.max(-1, dot / (n1 * n2)));

  return Math.round((Math.acos(cos) * 180) / Math.PI);

}



export function createPoseCamera({ video, canvas, onHint }) {

  let stream = null;

  let raf = 0;

  let running = false;

  let lastVideoTime = -1;

  let landmarker = null;



  async function start() {

    stream = await navigator.mediaDevices.getUserMedia({

      video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },

      audio: false,

    });

    video.src = "";

    video.srcObject = stream;

    await video.play();

    running = true;

    onHint?.("摄像头已开启，正在加载姿态模型…");

    try {

      landmarker = await getPoseLandmarker();

      onHint?.("姿态模型就绪：请站入画面（镜像预览）");

    } catch (e) {

      onHint?.("姿态模型加载失败，仅保留摄像头预览。" + (e?.message || ""));

    }

    loop();

  }



  async function loop() {

    if (!running) return;

    const ctx = canvas.getContext("2d");

    const w = video.videoWidth || 640;

    const h = video.videoHeight || 480;

    canvas.width = w;

    canvas.height = h;



    ctx.save();

    ctx.clearRect(0, 0, w, h);

    ctx.translate(w, 0);

    ctx.scale(-1, 1);

    ctx.drawImage(video, 0, 0, w, h);



    try {

      if (landmarker && video.currentTime !== lastVideoTime) {

        lastVideoTime = video.currentTime;

        const res = landmarker.detectForVideo(video, performance.now());

        const lm = res?.landmarks?.[0];

        if (lm) {

          drawSkeleton(ctx, lm, w, h, true);

          const kneeL = angle(lm[23], lm[25], lm[27]);

          const kneeR = angle(lm[24], lm[26], lm[28]);

          const knee = kneeL || kneeR;

          const hint = knee

            ? `膝角约 ${knee}° · ${knee < 70 ? "下蹲较深" : knee > 160 ? "接近站立" : "动作进行中"}`

            : "已检测到人体";

          onHint?.(hint);

        } else {

          onHint?.("未检测到人体，请正对摄像头、全身入画");

        }

      }

    } catch {

      /* 仅预览 */

    }

    ctx.restore();

    raf = requestAnimationFrame(loop);

  }



  function stop() {

    running = false;

    cancelAnimationFrame(raf);

    if (stream) {

      stream.getTracks().forEach((t) => t.stop());

      stream = null;

    }

    video.srcObject = null;

  }



  return { start, stop };

}


