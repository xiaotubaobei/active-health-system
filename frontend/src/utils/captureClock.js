// Measures camera capture time, not completed repetitions or exercise duration.
export function createCaptureClock(now = () => performance.now()) {
  let total = 0, since = null;
  return {
    start() { if (since === null) since = now(); },
    pause() { if (since !== null) { total += Math.max(0, now() - since); since = null; } },
    reset(ms = 0) { total = Number.isFinite(ms) && ms >= 0 ? ms : 0; since = null; },
    elapsed() { return Math.round(total + (since === null ? 0 : Math.max(0, now() - since))); },
  };
}
