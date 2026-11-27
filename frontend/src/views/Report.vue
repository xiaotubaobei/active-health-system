<template>
  <div class="card">
    <h2>训练报告</h2>
    <p class="muted">在这里选择每一次已完成的训练，查看动作分析、完成次数和训练建议。</p>

    <section class="report-picker" aria-labelledby="report-picker-title">
      <div class="picker-heading">
        <div>
          <h3 id="report-picker-title">选择训练报告</h3>
          <p>按完成时间从新到旧排列，共 {{ reportTotal }} 份报告（可能包含体验记录）。</p>
        </div>
        <button class="secondary" type="button" :disabled="listBusy" @click="loadReportList(false)">
          {{ listBusy ? "正在刷新…" : "刷新报告" }}
        </button>
      </div>

      <p v-if="listErr" class="err" role="alert">{{ listErr }}</p>
      <p v-if="listBusy && !reportSessions.length" class="muted">正在读取训练报告…</p>
      <div v-else-if="reportSessions.length" class="report-list" aria-label="训练报告列表">
        <button
          v-for="session in reportSessions"
          :key="session.id"
          type="button"
          class="report-option"
          :class="{ selected: Number(sessionId) === Number(session.id) }"
          :aria-pressed="Number(sessionId) === Number(session.id)"
          :disabled="busy || listBusy"
          @click="selectReport(session.id)"
        >
          <span>
            <strong>{{ session.exercise_name || "训练动作" }}</strong>
            <small>{{ formatTime(session.finished_at || session.started_at) }}</small>
          </span>
          <span class="report-number">训练 #{{ session.id }}</span>
        </button>
      </div>
      <div v-else-if="!listBusy && !listErr" class="empty-report">
        <p>还没有训练报告，完成第一次训练后会显示在这里。</p>
        <router-link class="report-link" to="/exercise">开始训练</router-link>
      </div>

      <div v-if="reportTotal > reportPageSize" class="report-pages">
        <button class="secondary" type="button" :disabled="listBusy || reportPage <= 1" @click="changeReportPage(-1)">上一页</button>
        <span>第 {{ reportPage }} / {{ Math.ceil(reportTotal / reportPageSize) }} 页</span>
        <button class="secondary" type="button" :disabled="listBusy || reportPage * reportPageSize >= reportTotal" @click="changeReportPage(1)">下一页</button>
      </div>
    </section>

    <router-link class="report-link secondary-link" to="/prescription">查看训练计划</router-link>
    <p v-if="err" class="err" role="alert">{{ err }}</p>
    <button v-if="err && sessionId" class="secondary" :disabled="busy" @click="reloadReport">重试读取报告</button>
    <p v-if="busy" class="muted" role="status">正在加载所选报告…</p>
    <div v-if="data" class="report-content">
      <h3>{{ data.session?.exercise_name || "动作" }} · 训练 #{{ data.session?.id }}</h3>
      <p class="muted">训练视频：{{ data.session?.video_path ? "已保存" : "未保存" }}</p>
      <p v-if="poseLine">{{ poseLine }}</p>
      <span class="tag" :class="{ gray: validScore == null }">{{ validScore != null ? "动作分析完成" : analysis.status === 'demo' ? "参考分析" : "暂时没有有效动作评分" }}</span>
      <p class="muted">{{ analysisMessage }}</p>
      <div class="stat"><span>动作分析评分</span><b>{{ validScore ?? "暂无有效评分" }}</b></div>
      <template v-if="validScore != null">
        <div class="score-bar"><i :style="{ width: validScore + '%' }"></i></div>
        <p>需要注意：<span class="tag" v-for="e in cot.errors || []" :key="e">{{ e }}</span><span v-if="!cot.errors?.length">服务未返回错误项</span></p>
        <p v-if="cot.advice">训练建议：{{ cot.advice }}</p>
        <h3>分析说明</h3>
        <ol><li v-for="(step, i) in cot.steps || []" :key="i">{{ step }}</li></ol>
      </template>
      <h3>完成次数与时间</h3>
      <template v-if="hasMotionCount">
        <p>完成次数：{{ motion.rep_count ?? "未返回" }}</p>
        <details v-if="motion.rep_intervals?.length"><summary>查看每次动作时间</summary>
          <p v-for="(interval, i) in motion.rep_intervals" :key="i">第 {{ i + 1 }} 次：{{ interval.start_sec }}–{{ interval.end_sec }} 秒</p>
        </details>
      </template>
      <p v-else class="muted">{{ motion.error || motion.message || "本次尚无可用的动作计数；不会用演示次数补齐。" }}</p>
      <SessionFeedback v-if="data.session?.id" ref="feedbackPanel" :key="data.session.id" :session-id="data.session.id" />
      <details class="analysis-details">
        <summary>查看原始服务结果（可能含演示数据）</summary>
        <p class="muted">此区域用于问题排查，日常查看训练报告时无需展开。</p>
        <pre style="white-space:pre-wrap;overflow-wrap:anywhere">{{ JSON.stringify(data.report, null, 2) }}</pre>
      </details>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import api, { getUser } from "../api/client";
import SessionFeedback from "../components/SessionFeedback.vue";

const route = useRoute();
const router = useRouter();
const user = getUser();
const sessionId = ref("");
const data = ref(null);
const err = ref("");
const busy = ref(false);
const feedbackPanel = ref(null);
function reloadReport() {
  if (!feedbackPanel.value || feedbackPanel.value.confirmLeave()) return loadReport();
}
const reportSessions = ref([]);
const reportTotal = ref(0);
const reportPage = ref(1);
const reportPageSize = 8;
const listBusy = ref(false);
const listErr = ref("");
let requestId = 0;
let listRequestId = 0;
const cot = computed(() => data.value?.report?.cot || {});
const analysis = computed(() => data.value?.analysis || { status: "unavailable", score: null });
const validScore = computed(() => analysis.value.status === "model" && typeof analysis.value.score === "number" && Number.isFinite(analysis.value.score) && analysis.value.score >= 0 && analysis.value.score <= 100 ? analysis.value.score : null);
const analysisMessage = computed(() => {
  if (validScore.value != null) return "本次动作分析已完成，结果仅供训练参考，不会自动调整训练计划。";
  if (analysis.value.status === "demo") return "当前结果仅用于体验，不计入训练评分，也不会调整训练计划。";
  return "本次暂时没有可用的动作分析结果，可以正常查看其他训练信息。";
});
const pose = computed(() => data.value?.session?.pose_summary || {});
const motion = computed(() => pose.value.motion_analysis || {});
const hasMotionCount = computed(() => motion.value.status === "ok" && Number.isInteger(motion.value.rep_count) && motion.value.rep_count >= 0);
const poseLine = computed(() => {
  const p = pose.value;
  const n = p.sequences?.coco17?.frames?.length || p.raw?.frame_count || 0;
  if (!n) return "本次没有可用的动作分析数据。";
  return "本次动作数据已记录，可用于生成动作分析。";
});
function reportErrorMessage(error) {
  const status = error?.response?.status;
  if (error?.code === "ECONNABORTED" || /timeout/i.test(error?.message || "") || [408, 504].includes(status)) {
    return "报告加载时间过长，请稍后重试。";
  }
  if (status === 404) return "报告不存在或当前账号无法查看，请从自己的训练记录重新选择。";
  if (!error?.response || status >= 500) return "暂时无法读取报告，请稍后重试。";
  return "报告读取失败，请稍后重试。";
}
function reportListErrorMessage(error) {
  const status = error?.response?.status;
  if (error?.code === "ECONNABORTED" || /timeout/i.test(error?.message || "") || [408, 504].includes(status)) {
    return "报告列表读取时间过长，请稍后重试。";
  }
  if (!error?.response || status >= 500) return "暂时无法读取报告列表，请稍后重试。";
  return "报告列表读取失败，请稍后重试。";
}
const formatTime = (value) => value
  ? new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(value) ? value : `${value}Z`).toLocaleString("zh-CN")
  : "时间未记录";

async function loadReport() {
  const current = ++requestId;
  data.value = null;
  err.value = "";
  if (!Number.isInteger(Number(sessionId.value)) || Number(sessionId.value) <= 0) {
    err.value = "请在上方选择一份训练报告。";
    busy.value = false;
    return;
  }
  busy.value = true;
  try {
    const response = await api.get(`/reports/${Number(sessionId.value)}`);
    if (current === requestId) data.value = response.data;
  } catch (error) {
    if (current === requestId) err.value = reportErrorMessage(error);
  } finally { if (current === requestId) busy.value = false; }
}

async function selectReport(id) {
  if (!Number.isInteger(Number(id)) || Number(id) <= 0) return;
  if (Number(route.query.session_id) === Number(id)) {
    sessionId.value = String(id);
    await reloadReport();
    return;
  }
  await router.replace({ path: "/report", query: { session_id: Number(id) } });
}

async function loadReportList(selectFirst = false) {
  const current = ++listRequestId;
  reportSessions.value = [];
  listBusy.value = true;
  listErr.value = "";
  try {
    const { data: pageData } = await api.get(`/users/${user.id}/sessions/page`, {
      params: { status: "finished", page: reportPage.value, page_size: reportPageSize },
    });
    if (current !== listRequestId) return;
    if (!Array.isArray(pageData.items)) throw new Error("报告列表格式不正确");
    reportSessions.value = pageData.items.filter((item) => Number.isInteger(Number(item.id)) && Number(item.id) > 0);
    reportTotal.value = Number(pageData.total) || 0;
    if ((selectFirst || !route.query.session_id) && reportSessions.value.length) {
      await selectReport(reportSessions.value[0].id);
    }
  } catch (error) {
    if (current === listRequestId) { reportTotal.value = 0; listErr.value = reportListErrorMessage(error); }
  } finally {
    if (current === listRequestId) listBusy.value = false;
  }
}

async function changeReportPage(delta) {
  if (listBusy.value) return;
  const next = reportPage.value + delta;
  if (next < 1 || next > Math.max(1, Math.ceil(reportTotal.value / reportPageSize))) return;
  reportPage.value = next;
  await loadReportList(false);
}

watch(() => route.query.session_id, (value) => {
  sessionId.value = value || "";
  if (sessionId.value) loadReport();
  else {
    ++requestId;
    busy.value = false;
    data.value = null;
    err.value = "";
  }
}, { immediate: true });
onMounted(() => loadReportList(false));
</script>

<style scoped>
.report-link {
  display: inline-block;
  padding: 8px 12px;
  border-radius: 6px;
  background: var(--accent);
  color: #fff;
  text-decoration: none;
}
.secondary-link { margin-top: 16px; background: #4a6358; }
.report-picker {
  margin-top: 20px;
  padding: 18px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.025);
}
.picker-heading { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.picker-heading h3 { margin: 0; }
.picker-heading p { margin: 6px 0 0; color: var(--muted); }
.report-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-top: 16px; }
.report-option {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  min-height: 70px;
  padding: 12px 14px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.035);
  color: inherit;
  text-align: left;
}
.report-option.selected { border-color: var(--accent); background: rgba(61, 165, 112, 0.13); }
.report-option strong,
.report-option small { display: block; }
.report-option small { margin-top: 5px; color: var(--muted); }
.report-number { flex: 0 0 auto; color: var(--muted); font-size: 0.88rem; }
.report-pages { display: flex; justify-content: center; gap: 12px; align-items: center; margin-top: 16px; }
.empty-report {
  margin: 18px 0 0;
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  color: var(--muted);
}
.empty-report p { margin-top: 0; }
.report-content { margin-top: 20px; padding-top: 18px; border-top: 1px solid var(--line); }
.analysis-details { margin-top: 16px; }
.analysis-details summary { cursor: pointer; }
@media (max-width: 700px) {
  .report-picker { padding: 14px; }
  .picker-heading { display: grid; grid-template-columns: minmax(0, 1fr); }
  .picker-heading button { width: 100%; }
  .report-list { grid-template-columns: minmax(0, 1fr); }
  .report-option { width: 100%; }
  .report-pages { flex-wrap: wrap; }
  .report-pages button { flex: 1 1 120px; }
}
</style>
