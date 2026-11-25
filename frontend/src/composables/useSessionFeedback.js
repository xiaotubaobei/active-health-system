import { computed, ref } from "vue";

const blank = () => ({ performed: "", completion: "", effort: "", discomfort: "", note: "" });
const snapshot = form => JSON.stringify(form);
function fromRecord(row) {
  return row ? {
    performed: row.performed ? "training" : "demo",
    completion: row.completion || "",
    effort: row.effort || "",
    discomfort: row.discomfort === true ? "yes" : row.discomfort === false ? "no" : "",
    note: row.note || "",
  } : blank();
}

// API and session id are supplied so races and failed connections can be checked without a browser.
export function useSessionFeedback({ api, sessionId, errorMessage }) {
  const form = ref(blank());
  const loaded = ref(false), loading = ref(false), saving = ref(false);
  const loadError = ref(""), saveError = ref(""), conflict = ref(false);
  const revision = ref(0), savedAt = ref("");
  const baseline = ref(snapshot(form.value));
  const dirty = computed(() => loaded.value && snapshot(form.value) !== baseline.value);
  let generation = 0, disposed = false;

  function participationChanged() {
    if (form.value.performed === "demo") {
      form.value.completion = "";
      form.value.effort = "";
      form.value.discomfort = "";
    }
  }

  async function load() {
    if (disposed) return;
    const current = ++generation;
    loading.value = true; saving.value = false; loaded.value = false;
    loadError.value = ""; saveError.value = ""; conflict.value = false;
    try {
      const { data } = await api.get(`/sessions/${sessionId()}/feedback`);
      if (disposed || current !== generation) return;
      const row = data.feedback;
      form.value = fromRecord(row);
      baseline.value = snapshot(form.value);
      revision.value = row?.revision || 0;
      savedAt.value = row?.updated_at || "";
      loaded.value = true;
    } catch (error) {
      if (!disposed && current === generation) loadError.value = errorMessage(error, "反馈读取失败，请重新加载。暂时不能填写，避免覆盖已有反馈。");
    } finally { if (!disposed && current === generation) loading.value = false; }
  }

  async function save() {
    if (disposed || !loaded.value || loading.value || saving.value || conflict.value || !dirty.value) return;
    const values = form.value;
    if (!["training", "demo"].includes(values.performed)) {
      saveError.value = "请先选择这次是本人实际训练，还是仅体验样本。";
      return;
    }
    const performed = values.performed === "training";
    if (performed && (!["completed", "partial", "stopped"].includes(values.completion)
      || !["easy", "moderate", "hard"].includes(values.effort)
      || !["yes", "no"].includes(values.discomfort))) {
      saveError.value = "请填完整：完成情况、费力程度、是否有不适。";
      return;
    }
    if (values.note.length > 1000) { saveError.value = "补充说明最多1000字。"; return; }
    const submission = {
      expected_revision: revision.value, performed,
      completion: performed ? values.completion : null,
      effort: performed ? values.effort : null,
      discomfort: performed ? values.discomfort === "yes" : null,
      note: values.note.trim(),
    };
    const current = generation, sentForm = snapshot(values);
    saving.value = true; saveError.value = "";
    try {
      const { data } = await api.put(`/sessions/${sessionId()}/feedback`, submission);
      if (disposed || current !== generation) return;
      const savedForm = fromRecord(data.feedback);
      baseline.value = snapshot(savedForm);
      if (snapshot(form.value) === sentForm) form.value = savedForm;
      revision.value = data.feedback.revision;
      savedAt.value = data.feedback.updated_at;
    } catch (error) {
      if (!disposed && current === generation) {
        conflict.value = error?.response?.status === 409;
        saveError.value = errorMessage(error, "反馈未确认保存，内容还在本页。请保持页面打开并重试。");
      }
    } finally { if (!disposed && current === generation) saving.value = false; }
  }

  function dispose() { disposed = true; generation++; }
  return { form, loaded, loading, saving, loadError, saveError, conflict, revision, savedAt, dirty,
    participationChanged, load, save, dispose };
}
