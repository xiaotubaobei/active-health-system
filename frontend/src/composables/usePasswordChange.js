import { ref } from "vue";

// Keep passwords only in this mounted form. No browser storage or automatic retries.
export function usePasswordChange({ api, errorMessage, onChanged, onSignIn, now = Date.now }) {
  const current = ref(""), next = ref(""), confirmation = ref("");
  const busy = ref(false), error = ref(""), uncertain = ref(false), changed = ref(false);
  const retryAt = ref(0);
  let disposed = false;
  function clear() { current.value = ""; next.value = ""; confirmation.value = ""; }
  async function submit() {
    if (disposed || busy.value || uncertain.value || changed.value) return;
    error.value = "";
    if (now() < retryAt.value) { error.value = `请再等 ${Math.ceil((retryAt.value - now()) / 1000)} 秒后提交。`; return; }
    if (!current.value || !next.value || !confirmation.value) { error.value = "请把三项密码填写完整。"; return; }
    if (next.value.length < 8 || next.value.length > 128 || current.value.length > 128) { error.value = "新密码需要 8–128 个字符。"; return; }
    if (next.value !== confirmation.value) { error.value = "两次新密码不一致，请重新确认。"; return; }
    if (next.value === current.value) { error.value = "新密码不能与当前密码相同。"; return; }
    busy.value = true;
    try {
      await api.post("/auth/change-password", { current_password: current.value, new_password: next.value }, { skipAuthRedirect: true });
      clear();
      if (!disposed) {
        changed.value = true;
        try { await onChanged(); }
        catch { if (!disposed) error.value = "密码已修改，请点击下方按钮前往登录。"; }
      }
    } catch (e) {
      clear();
      if (disposed) return;
      const status = e?.response?.status;
      if (status === 401) { await onSignIn(); return; }
      if (!status || status >= 500 || status === 409) {
        uncertain.value = true;
        error.value = "修改结果未确认，请重新登录：先尝试新密码，如不成功再用原密码。";
      } else {
        if (status === 429) {
          const seconds = Number(e.response.headers?.["retry-after"]);
          retryAt.value = now() + (Number.isFinite(seconds) && seconds > 0 ? seconds : 60) * 1000;
        }
        error.value = errorMessage(e, "修改未成功，请检查密码后重新填写。");
      }
    } finally { busy.value = false; }
  }
  function dispose() { disposed = true; clear(); }
  return { current, next, confirmation, busy, error, uncertain, changed, submit, dispose };
}
