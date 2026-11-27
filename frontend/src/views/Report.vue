<template>
  <section class="card report-page" :aria-busy="viewState === 'loading'">
    <header class="report-header">
      <h2>训练报告</h2>
      <router-link class="report-link secondary" to="/history">查看训练历史</router-link>
    </header>

    <p v-if="viewState === 'loading'" class="loading-state muted" role="status">正在加载训练报告，请稍候…</p>

    <section v-else-if="viewState !== 'ready'" class="empty-state" :role="viewState === 'empty' ? 'status' : 'alert'">
      <h3>{{ stateTitle }}</h3>
      <p class="muted">{{ stateMessage }}</p>
      <div class="row report-actions">
        <button v-if="viewState === 'failed'" type="button" @click="load">重新加载</button>
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
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRoute } from "vue-router";
import api, { errorMessage, getUser } from "../api/client";

const route = useRoute();
const data = ref(null);
const viewState = ref("loading");
const loadError = ref("");
let requestId = 0;
let controller;

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
  forbidden: "当前账号无法查看这份报告", unauthorized: "登录已失效", failed: "报告加载失败",
}[viewState.value] || "报告暂不可用"));
const stateMessage = computed(() => ({
  empty: "还没有已完成训练的记录。完成训练后可从训练历史查看报告。",
  invalid: "请从训练历史选择要查看的报告，无需手动填写训练编号。",
  not_found: "该记录可能尚未生成报告，或当前账号没有访问权限。请回到训练历史选择可用报告。",
  forbidden: "请回到训练历史查看当前账号的记录。",
  unauthorized: "请重新登录后查看自己的训练记录。",
  failed: loadError.value,
}[viewState.value] || "请从训练历史选择一份报告。"));

function formatTime(value) {
  if (typeof value !== "string" || !value) return "时间未记录";
  const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}Z`;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? "时间未记录" : date.toLocaleString("zh-CN");
}

async function load() {
  const current = ++requestId;
  controller?.abort();
  controller = new AbortController();
  const signal = controller.signal;
  data.value = null;
  loadError.value = "";
  viewState.value = "loading";
  const requestedId = route.query.session_id;
  let sessionId;
  try {
    if (requestedId === undefined) {
      const user = getUser();
      if (!user?.id) {
        viewState.value = "unauthorized";
        return;
      }
      const history = await api.get(`/users/${user.id}/sessions/page`, {
        params: { page: 1, page_size: 1, status: "finished" }, signal,
      });
      if (current !== requestId) return;
      if (!Array.isArray(history.data.items)) throw new Error("报告记录数据不完整");
      if (!history.data.items.length) {
        viewState.value = "empty";
        return;
      }
      sessionId = history.data.items[0].id;
    } else {
      if (typeof requestedId !== "string" || !/^[1-9]\d*$/.test(requestedId)) {
        viewState.value = "invalid";
        return;
      }
      sessionId = Number(requestedId);
    }
    if (!Number.isSafeInteger(sessionId) || sessionId <= 0) {
      viewState.value = "invalid";
      return;
    }
    const response = await api.get(`/reports/${sessionId}`, { signal });
    if (current !== requestId) return;
    if (response.data?.session?.id !== sessionId || !response.data?.report) throw new Error("报告数据不完整");
    data.value = response.data;
    viewState.value = "ready";
  } catch (error) {
    if (current !== requestId || signal.aborted) return;
    viewState.value = ({ 401: "unauthorized", 403: "forbidden", 404: "not_found" })[error?.response?.status] || "failed";
    loadError.value = errorMessage(error, "报告暂时无法读取，请检查连接后重新加载。");
  }
}
watch(() => route.query.session_id, load, { immediate: true });
onBeforeUnmount(() => {
  requestId += 1;
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
</style>
