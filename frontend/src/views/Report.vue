<template>
  <section class="card report-page" :aria-busy="viewState === 'loading'">
    <header class="report-header">
      <h2>训练报告</h2>
      <router-link class="report-link secondary" to="/history">查看训练历史</router-link>
    </header>

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

    <p v-if="viewState === 'loading'" class="loading-state muted" role="status">正在加载训练报告，请稍候…</p>

    <section v-else-if="viewState !== 'ready'" class="empty-state" :role="viewState === 'empty' ? 'status' : 'alert'">
      <h3>{{ stateTitle }}</h3>
      <p class="muted">{{ stateMessage }}</p>
      <div class="row report-actions">
        <button v-if="viewState === 'failed'" type="button" @click="reloadReport">重新加载</button>
        <button v-if="viewState === 'list_failed'" type="button" @click="loadReportList(false)">重新加载报告列表</button>
        <router-link v-if="viewState === 'unauthorized'" class="report-link" to="/login">重新登录</router-link>
        <router-link v-else class="report-link" to="/exercise">开始训练</router-link>
        <router-link class="report-link secondary" to="/history">查看训练历史</router-link>
      </div>
    </section>

    <article v-else :key="data.session.id">
      <p v-if="route.query.session_id === undefined" class="muted">正在显示最近完成的一次训练。</p>
      <div class="training-heading">
        <h3>{{ data.session.exercise_name || data.session.exercise_id || "训练动作" }}</h3>
        <span class="tag gray">{{ trainingStatus }}</span>
        <button type="button" class="secondary" :disabled="busy" @click="reloadReport">重新读取本次报告</button>
      </div>
      <dl class="training-times">
        <div><dt>开始时间</dt><dd>{{ formatTime(data.session.started_at) }}</dd></div>
        <div><dt>结束时间</dt><dd>{{ formatTime(data.session.finished_at) }}</dd></div>
      </dl>

      <section class="report-section" aria-labelledby="assessment-heading">
        <h3 id="assessment-heading">本次评估</h3>
        <span class="tag" :class="{ gray: !hasModelScore }">{{ assessmentLabel }}</span>
        <p>{{ assessmentMessage }}</p>
        <div class="result-grid">
          <div v-if="hasModelScore" class="stat">
            <span>模型评估分</span><b>{{ analysis.score }} 分</b>
          </div>
          <div v-else class="stat">
            <span>模型评估分</span><b class="unavailable-value">暂无有效评分</b>
          </div>
          <div class="stat">
            <span>动作计数</span>
            <b v-if="repCount !== null">{{ repCount }} 次</b>
            <b v-else class="unavailable-value">未获取</b>
          </div>
        </div>
        <p v-if="repCount !== null" class="muted">次数为本次计数服务返回的识别结果，不代表整套训练计划已完成。</p>
        <p v-else class="muted">{{ countMessage }}</p>
        <p class="muted">{{ poseMessage }}</p>
      </section>

      <section class="report-section" aria-labelledby="advice-heading">
        <h3 id="advice-heading">问题与建议</h3>
        <template v-if="hasModelScore">
          <h4>模型返回的问题</h4>
          <ul v-if="modelErrors.length" class="model-errors">
            <li v-for="(issue, index) in modelErrors" :key="index">{{ issue }}</li>
          </ul>
          <p v-else class="muted">模型未返回问题项，不能据此判断动作完全正确。</p>
          <h4>模型建议</h4>
          <p v-if="modelAdvice" class="advice-text">{{ modelAdvice }}</p>
          <p v-else class="muted">本次未返回模型建议。</p>
        </template>
        <p v-else class="muted">本次没有有效模型评估，暂不提供个性化动作问题或建议。可以查看训练计划，再从训练历史回看记录。</p>
        <div class="row report-actions">
          <router-link class="report-link" to="/prescription">查看训练计划</router-link>
          <router-link class="report-link secondary" to="/exercise">开始训练</router-link>
        </div>
      </section>

      <SessionFeedback v-if="data.session?.status === 'finished'" ref="feedbackPanel" :key="data.session.id" :session-id="data.session.id" />

      <details v-if="repCount > 0 && repIntervals.length" class="report-details">
        <summary>查看每次动作的时间区间</summary>
        <ol class="interval-list">
          <li v-for="interval in repIntervals" :key="interval.index">
            第 {{ interval.index }} 次：{{ interval.start_sec }}–{{ interval.end_sec }} 秒
          </li>
        </ol>
      </details>
      <details class="report-details">
        <summary>查看数据详情与原始服务结果</summary>
        <p class="muted">其中可能包含演示或备用内容，评估分数和次数以上方标注的结果为准。</p>
        <p class="muted">训练编号：#{{ data.session.id }}</p>
        <p class="muted">视频引用：{{ data.session.video_path || "未保存视频引用" }}</p>
        <h4 v-if="hasModelScore && modelSteps.length">模型返回的分析说明</h4>
        <ol v-if="hasModelScore && modelSteps.length">
          <li v-for="(step, index) in modelSteps" :key="index">{{ step }}</li>
        </ol>
        <pre>{{ rawResults }}</pre>
      </details>
    </article>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
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
const errorKind = ref("failed");
const viewState = computed(() => busy.value || (listBusy.value && !sessionId.value) ? "loading"
  : data.value ? "ready" : err.value ? errorKind.value : listErr.value && !sessionId.value ? "list_failed" : "empty");
const loadError = err;
let controller;
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
const analysis = computed(() => data.value?.analysis || {});
const pose = computed(() => data.value?.session?.pose_summary || {});
const motion = computed(() => pose.value.motion_analysis || {});
const hasModelScore = computed(() => analysis.value.status === "model"
  && typeof analysis.value.score === "number" && Number.isFinite(analysis.value.score)
  && analysis.value.score >= 0 && analysis.value.score <= 100);
const assessmentLabel = computed(() => hasModelScore.value ? "有效模型评估"
  : analysis.value.status === "demo" ? "演示 / 备用结果" : "暂无有效评估");
const assessmentMessage = computed(() => {
  if (hasModelScore.value) return "本次分数由模型服务返回，请结合下方问题与建议查看。";
  if (analysis.value.status === "demo") {
    return analysis.value.mode === "local_fallback"
      ? "评估服务未提供有效模型结果，本次使用备用结果；不计分、不参与成绩比较。"
      : "本次为演示结果；不计分、不参与成绩比较，也不作为个性化动作建议。";
  }
  return "本次评估结果不完整或来源未确认，暂无有效评分。";
});

function textItems(value) {
  return Array.isArray(value) ? value.filter((item) => typeof item === "string" && item.trim()) : [];
}
const modelErrors = computed(() => hasModelScore.value ? textItems(cot.value.errors) : []);
const modelAdvice = computed(() => hasModelScore.value && typeof cot.value.advice === "string" ? cot.value.advice.trim() : "");
const modelSteps = computed(() => hasModelScore.value ? textItems(cot.value.steps) : []);
const repCount = computed(() => motion.value.status === "ok"
  && Number.isSafeInteger(motion.value.rep_count) && motion.value.rep_count >= 0 ? motion.value.rep_count : null);
const countMessage = computed(() => {
  if (motion.value.status === "failed") return "本次动作计数失败，未获取次数。";
  if (motion.value.status === "ok") return "计数结果缺少有效的非负整数次数，暂不展示。";
  return "本次报告未获取动作计数结果。";
});
const repIntervals = computed(() => {
  if (repCount.value === null || !Array.isArray(motion.value.rep_intervals)) return [];
  return motion.value.rep_intervals.map((interval, index) => ({ ...interval, index: index + 1 }))
    .filter((interval) => interval.index <= repCount.value
      && Number.isFinite(interval.start_sec) && Number.isFinite(interval.end_sec)
      && interval.start_sec >= 0 && interval.end_sec >= interval.start_sec);
});

const poseMessage = computed(() => {
  const p = pose.value;
  if (["mock", "local_fallback", "stub_single_frame"].includes(p.mode) || p.source === "demo") {
    return "本次仅保存了演示或备用姿态信息。";
  }
  const sequences = p.sequences || {};
  const cocoFrames = Array.isArray(sequences.coco17?.frames) ? sequences.coco17.frames.length : 0;
  const mpFrames = Array.isArray(sequences.mediapipe33?.frames) ? sequences.mediapipe33.frames.length : 0;
  const rawFrames = Number.isSafeInteger(p.raw?.frame_count) && p.raw.frame_count > 0 ? p.raw.frame_count : 0;
  const frameCount = cocoFrames || mpFrames || rawFrames;
  return frameCount ? `已保存 ${frameCount} 帧姿态记录；帧数不代表动作次数。` : "本次未保存姿态帧，无法在报告中回看姿态记录。";
});
const trainingStatus = computed(() => ({ running: "未完成", finished: "已完成", cancelled: "已取消" }[data.value?.session?.status] || "状态未记录"));
const rawResults = computed(() => JSON.stringify({ analysis: analysis.value, report: data.value?.report, motion_analysis: motion.value }, null, 2));

const stateTitle = computed(() => ({
  empty: "暂无可查看的报告", invalid: "训练编号无效", not_found: "报告不存在或当前账号无法访问",
  forbidden: "当前账号无法查看这份报告", unauthorized: "登录已失效", failed: "报告加载失败", list_failed: "报告列表加载失败",
}[viewState.value] || "报告暂不可用"));
const stateMessage = computed(() => ({
  empty: "还没有已完成训练的记录。完成训练后可从训练历史查看报告。",
  invalid: "请从训练历史选择要查看的报告，无需手动填写训练编号。",
  not_found: "该记录可能尚未生成报告，或当前账号没有访问权限。请回到训练历史选择可用报告。",
  forbidden: "请回到训练历史查看当前账号的记录。",
  unauthorized: "请重新登录后查看自己的训练记录。",
  failed: loadError.value,
  list_failed: listErr.value,
}[viewState.value] || "请从训练历史选择一份报告。"));

function formatTime(value) {
  if (typeof value !== "string" || !value) return "时间未记录";
  const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}Z`;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? "时间未记录" : date.toLocaleString("zh-CN");
}

const validScore = computed(() => hasModelScore.value ? analysis.value.score : null);
const hasMotionCount = computed(() => repCount.value !== null);
const analysisMessage = assessmentMessage;
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
async function loadReport() {
  const current = ++requestId;
  controller?.abort();
  controller = new AbortController();
  const signal = controller.signal;
  data.value = null;
  err.value = "";
  if (Array.isArray(sessionId.value) || !/^[1-9]\d*$/.test(String(sessionId.value)) || !Number.isSafeInteger(Number(sessionId.value))) {
    errorKind.value = "invalid";
    err.value = "请在上方选择一份训练报告。";
    busy.value = false;
    return;
  }
  busy.value = true;
  try {
    const response = await api.get(`/reports/${Number(sessionId.value)}`, { signal });
    if (current !== requestId || signal.aborted) return;
    if (response.data?.session?.id !== Number(sessionId.value) || !response.data?.report) throw new Error("报告数据不完整");
    data.value = response.data;
  } catch (error) {
    if (current === requestId && !signal.aborted) {
      errorKind.value = ({ 401: "unauthorized", 403: "forbidden", 404: "not_found" })[error?.response?.status] || "failed";
      err.value = reportErrorMessage(error);
    }
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
    if (!Array.isArray(pageData?.items) || !Number.isSafeInteger(pageData.total) || pageData.total < 0) throw new Error("报告列表格式不正确");
    if (!pageData.items.every(item => item && Number.isSafeInteger(item.id) && item.id > 0)) throw new Error("报告列表格式不正确");
    reportSessions.value = pageData.items;
    reportTotal.value = Number(pageData.total) || 0;
    if ((selectFirst || route.query.session_id === undefined) && reportSessions.value.length) {
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
  if (value !== undefined) loadReport();
  else {
    ++requestId;
    busy.value = false;
    data.value = null;
    err.value = "";
  }
}, { immediate: true });
onMounted(() => loadReportList(false));
onBeforeUnmount(() => {
  ++requestId;
  ++listRequestId;
  controller?.abort();
});
</script>

<style scoped>
.report-page { min-width: 0; overflow-wrap: anywhere; }
.report-header, .training-heading { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
.report-header { justify-content: space-between; margin-bottom: 20px; }
.report-header h2, .training-heading h3 { margin: 0; }
.training-heading h3 { font-size: 22px; }
.training-times { display: flex; flex-wrap: wrap; gap: 12px 28px; margin: 16px 0; }
.training-times dt { margin-bottom: 4px; color: var(--muted); font-size: 14px; }
.training-times dd { margin: 0; }
.report-section { margin-top: 24px; }
.report-section h3 { margin-bottom: 12px; }
.report-section h4 { margin: 16px 0 8px; }
.result-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.result-grid .stat { min-width: 0; }
.result-grid .unavailable-value { font-size: 18px; color: var(--muted); }
.advice-text { white-space: pre-wrap; }
.model-errors, .interval-list { padding-left: 22px; }
.model-errors li, .interval-list li { margin-bottom: 8px; }
.report-actions { margin-top: 16px; }
.report-link { display: inline-flex; justify-content: center; align-items: center; min-height: 44px; padding: 8px 12px; border-radius: 8px; background: var(--accent); color: white; }
.report-link.secondary { background: #4a6358; }
.report-link:focus-visible, summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
.report-details { margin-top: 24px; border-top: 1px solid var(--line); }
.report-details summary { display: list-item; cursor: pointer; min-height: 44px; padding: 12px 0; }
.report-details pre { max-height: 400px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; padding: 12px; border: 1px solid var(--line); border-radius: 8px; background: var(--bg); }
.loading-state, .empty-state { padding: 24px 0; }
.empty-state h3 { margin-top: 0; }
.report-page button { min-height: 44px; }
@media (max-width: 600px) {
  .result-grid { grid-template-columns: minmax(0, 1fr); }
  .training-times { flex-direction: column; }
  .report-actions { align-items: stretch; flex-direction: column; }
  .report-actions > * { width: 100%; }
}


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
