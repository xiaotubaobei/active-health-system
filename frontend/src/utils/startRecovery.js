// Per-tab recovery survives reloads without storing video, pose frames or credentials.
export function createStartRecovery({ storage, userId, api, randomKey }) {
  const storageKey = `ah_pending_start:${userId}`;
  function read() {
    const raw = storage.getItem(storageKey);
    if (!raw) return null;
    try {
      const value = JSON.parse(raw);
      if (typeof value.start_key !== 'string' || !/^[A-Za-z0-9_-]{16,64}$/.test(value.start_key) ||
          typeof value.exercise_id !== 'string' || !value.exercise_id ||
          !Number.isInteger(value.prescription_id) || value.prescription_id < 0 ||
          !['camera', 'video'].includes(value.input_mode)) throw new Error('invalid intent');
      return { start_key: value.start_key, exercise_id: value.exercise_id,
        prescription_id: value.prescription_id, input_mode: value.input_mode };
    } catch {
      storage.removeItem(storageKey);
      return null;
    }
  }
  return {
    read,
    begin({ exercise_id, prescription_id, input_mode }) {
      const previous = read();
      if (previous) {
        if (previous.exercise_id !== exercise_id || previous.prescription_id !== prescription_id || previous.input_mode !== input_mode) {
          throw new Error('请先检查上次开始结果，再选择其他训练。');
        }
        return previous;
      }
      const intent = { start_key: randomKey(), exercise_id, prescription_id, input_mode };
      // Save before sending: a reload immediately after the request can still find it.
      try { storage.setItem(storageKey, JSON.stringify(intent)); }
      catch { throw new Error('浏览器无法保存开始记录，请允许本站保存数据后重试。'); }
      return intent;
    },
    async lookup(intent) {
      try {
        return (await api.get(`/sessions/start-requests/${intent.start_key}`)).data.session;
      } catch (error) {
        if (error?.response?.status === 404) return null;
        throw error;
      }
    },
    clear(key) {
      if (read()?.start_key === key) storage.removeItem(storageKey);
    },
  };
}
