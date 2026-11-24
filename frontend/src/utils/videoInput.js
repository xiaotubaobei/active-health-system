export const MAX_VIDEO_BYTES = 100 * 1024 * 1024;
export const MAX_VIDEO_SECONDS = 180;

export function validateVideoFile(file) {
  if (!file || !file.size) throw new Error('请选择非空视频文件');
  if (file.size > MAX_VIDEO_BYTES) throw new Error('视频不能超过100MB，请先截取较短片段');
  if (file.type && !file.type.startsWith('video/')) throw new Error('请选择视频文件');
}

export function checkAborted(signal) {
  if (signal?.aborted) throw new DOMException('已取消视频解析', 'AbortError');
}

// Shared model loading continues for other users of the model, but this caller can leave immediately.
export function abortable(promise, signal) {
  checkAborted(signal);
  if (!signal) return promise;
  return new Promise((resolve, reject) => {
    const abort = () => reject(new DOMException('已取消视频解析', 'AbortError'));
    signal.addEventListener('abort', abort, { once: true });
    Promise.resolve(promise).then(resolve, reject).finally(() => signal.removeEventListener('abort', abort));
  });
}

function waitForVideo(video, { signal, timeoutMs, ready, start, message }) {
  checkAborted(signal);
  return new Promise((resolve, reject) => {
    let timer;
    const events = ['loadedmetadata', 'loadeddata', 'canplay', 'seeked'];
    const clean = () => {
      clearTimeout(timer);
      events.forEach(event => video.removeEventListener(event, check));
      video.removeEventListener('error', fail);
      signal?.removeEventListener('abort', abort);
    };
    const done = error => { clean(); error ? reject(error) : resolve(); };
    const check = () => { if (ready()) done(); };
    const fail = () => done(new Error('无法读取视频，请换用可播放的MP4文件'));
    const abort = () => done(new DOMException('已取消视频解析', 'AbortError'));
    events.forEach(event => video.addEventListener(event, check));
    video.addEventListener('error', fail);
    signal?.addEventListener('abort', abort, { once: true });
    timer = setTimeout(() => done(new Error(message)), timeoutMs);
    try { start(); check(); } catch (error) { done(error); }
  });
}

export function loadVideoSource(video, src, { signal, timeoutMs = 15000 } = {}) {
  return waitForVideo(video, { signal, timeoutMs,
    ready: () => video.readyState >= 2 && video.videoWidth > 0,
    start: () => {
      video.pause(); video.srcObject = null; video.preload = 'auto';
      video.src = src; video.load();
    },
    message: '视频加载超时，请换用较短的MP4文件后重试',
  });
}

export function seekVideo(video, time, { signal, timeoutMs = 10000 } = {}) {
  return waitForVideo(video, { signal, timeoutMs,
    ready: () => !video.seeking && video.readyState >= 2 && Math.abs(video.currentTime - time) < 0.1,
    start: () => {
      // Seeking to the initial position may not fire seeked; use the already decoded frame.
      if (video.seeking || Math.abs(video.currentTime - time) >= 0.001) video.currentTime = time;
    },
    message: '视频画面读取超时，请取消后换用较短的MP4文件',
  });
}
