// A released or denied lock never retries itself: the user may have enabled battery saving.
export function createScreenAwake({ navigator = globalThis.navigator, document = globalThis.document, onChange = () => {} } = {}) {
  let active = false, disposed = false, generation = 0, held = null, pending = null;
  const hidden = () => document?.visibilityState === 'hidden';
  const release = async lock => { try { await lock?.release(); } catch { /* already released */ } };

  function setActive(enabled) {
    active = !!enabled && !disposed && !hidden();
    if (!active) {
      generation++;
      const previous = held;
      held = null;
      onChange('idle');
      return release(previous).then(() => false);
    }
    if (!navigator?.wakeLock?.request) {
      onChange('unsupported');
      return Promise.resolve(false);
    }
    if (held && !held.released) return Promise.resolve(true);
    if (pending?.token === generation) return pending.promise;
    const token = ++generation;
    onChange('requesting');
    const promise = (async () => {
      // Defer the call so pending is assigned even when a browser throws synchronously.
      await Promise.resolve();
      try {
        if (!active || disposed || hidden() || token !== generation) return false;
        const acquired = await navigator.wakeLock.request('screen');
        if (!active || disposed || hidden() || token !== generation) {
          await release(acquired);
          return false;
        }
        if (acquired.released) { onChange('unavailable'); return false; }
        held = acquired;
        acquired.addEventListener('release', () => {
          if (held !== acquired) return;
          held = null;
          onChange(active && !hidden() ? 'unavailable' : 'idle');
        }, { once: true });
        onChange('active');
        return true;
      } catch {
        if (token === generation && active && !disposed) onChange('unavailable');
        return false;
      } finally {
        if (pending?.token === token) pending = null;
      }
    })();
    pending = { token, promise };
    return promise;
  }

  function dispose() { disposed = true; return setActive(false); }
  return { setActive, dispose };
}
