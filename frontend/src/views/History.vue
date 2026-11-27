<template>
  <section class="history-page">
    <header class="history-header">
      <div>
        <h2>训练历史</h2>
        <p class="muted">查看训练动作、时间、状态和对应报告。</p>
      </div>
      <button class="secondary" type="button" :disabled="busy" @click="load">
        {{ busy ? "正在读取…" : "重新加载" }}
      </button>
    </header>

    <p v-if="busy && sessions === null" class="muted" role="status">正在加载训练历史…</p>
    <div v-if="listErr" class="notice error-notice" role="alert">
      <span>{{ sessions === null ? listErr : `历史记录刷新失败：${listErr} 当前仍显示上次读取的内容。` }}</span>
      <button class="secondary" type="button" :disabled="busy" @click="load">重试</button>
    </div>

    <section v-if="summary" class="summary-section" aria-label="训练统计">
      <div class="summary-stat"><span>已完成训练</span><strong>{{ summary.finished_sessions }}</strong></div>
      <div class="summary-stat"><span>已归档记录</span><strong>{{ summary.kb_entries }}</strong></div>
      <div class="summary-stat"><span>最近模型均分</span><strong>{{ summary.avg_score_recent ?? "暂无" }}</strong></div>
      <p class="muted summary-caption">
        最近 20 条归档中，有效模型评估 {{ summary.scored_entries_recent }} 条；演示和备用结果不计入均分。
      </p>
    </section>
    <div v-if="summaryErr" class="notice muted-notice" role="status">
      <span>训练统计暂时无法读取：{{ summaryErr }}</span>
      <button class="secondary" type="button" :disabled="busy" @click="load">重试</button>
    </div>

    <template v-if="sessions !== null">
      <section class="history-controls" aria-label="筛选训练记录">
        <label>
          状态
          <select v-model="status" :disabled="busy" @change="resetPage">
            <option value="">全部状态</option>
            <option value="running">未完成</option>
            <option value="finished">已完成</option>
            <option value="cancelled">已取消</option>
          </select>
        </label>
        <label>
          动作
          <select v-model="exerciseId" :disabled="busy" @change="resetPage">
            <option value="">全部动作</option>
            <option v-for="exercise in exerciseOptions" :key="exercise.id" :value="exercise.id">
              {{ exercise.name }}
            </option>
          </select>
        </label>
        <span class="muted result-count">{{ total }} 条记录 · 第 {{ page }} / {{ pageCount }} 页</span>
        <button v-if="hasFilters" class="secondary" type="button" :disabled="busy" @click="clearFilters">
          清除筛选
        </button>
      </section>

      <div v-if="countErr" class="notice muted-notice" role="status">
        <span>{{ sessions.length ? `全部记录数量暂时无法读取：${countErr}` : `当前筛选下没有记录，暂时无法确认是否还有其他训练记录：${countErr}` }}</span>
        <div class="notice-actions">
          <button v-if="hasFilters" class="secondary" type="button" :disabled="busy" @click="clearFilters">清除筛选</button>
          <button class="secondary" type="button" :disabled="busy" @click="load">重试</button>
        </div>
      </div>

      <section v-if="sessions.length" class="history-list" aria-label="训练记录">
        <article v-for="session in sessions" :key="session.id" class="history-entry">
          <div class="entry-main">
            <div class="entry-title-line">
              <h3>{{ session.exercise_name || session.exercise_id || "训练动作" }}</h3>
              <span class="status-label" :class="`status-${session.status}`">{{ statusName(session.status) }}</span>
            </div>
            <time class="entry-time" :datetime="timeValue(session.finished_at || session.started_at)">
              {{ formatTime(session.finished_at || session.started_at) }}
            </time>
            <p v-if="session.status === 'finished'" class="assessment-line" :class="`assessment-${assessmentStatus(session)}`">
              {{ assessmentText(session) }}
            </p>
            <p v-if="session.history_note" class="history-note muted">{{ session.history_note }}</p>
            <span class="session-id muted">记录编号 #{{ session.id }}</span>
          </div>
          <div class="entry-actions">
            <router-link v-if="session.status === 'running'" class="action-link" :to="{ path: '/exercise', query: { session_id: session.id } }">
              继续训练
            </router-link>
            <router-link v-else-if="session.status === 'finished'" class="action-link" :to="{ path: '/report', query: { session_id: session.id } }">
              查看报告
            </router-link>
            <span v-else-if="session.status === 'cancelled'" class="muted">本次训练已取消</span>
          </div>
        </article>
      </section>

      <section v-else-if="!busy && total === 0 && hasFilters && allSessionTotal > 0" class="empty-state">
        <h3>当前筛选条件下没有记录</h3>
        <p class="muted">可以清除筛选查看全部训练记录。</p>
        <button class="secondary" type="button" @click="clearFilters">清除筛选</button>
      </section>

      <section v-else-if="!busy && total === 0 && allSessionTotal === null && countErr" class="empty-state">
        <h3>暂时无法确认训练记录</h3>
        <p class="muted">全部记录数量读取失败，请重新加载。</p>
        <div class="notice-actions">
          <button v-if="hasFilters" class="secondary" type="button" @click="clearFilters">清除筛选</button>
          <button class="secondary" type="button" :disabled="busy" @click="load">重新加载</button>
        </div>
      </section>

      <section v-else-if="!busy && total === 0 && allSessionTotal === 0" class="empty-state">
        <h3>还没有训练记录</h3>
        <p class="muted">完成一次训练后，记录和报告会显示在这里。</p>
        <router-link to="/exercise"><button type="button">开始训练</button></router-link>
      </section>

      <section v-else-if="!busy && !sessions.length && total > 0" class="empty-state">
        <h3>这一页没有记录</h3>
        <p class="muted">可能有新记录改变了分页位置，请返回上一页或重新加载。</p>
        <button class="secondary" type="button" :disabled="busy || page <= 1" @click="changePage(-1)">上一页</button>
      </section>

      <nav v-if="total > 0" class="pagination" aria-label="训练历史分页">
        <button class="secondary" type="button" :disabled="busy || page <= 1" @click="changePage(-1)">上一页</button>
        <span class="muted">第 {{ page }} / {{ pageCount }} 页</span>
        <button class="secondary" type="button" :disabled="busy || page >= pageCount" @click="changePage(1)">下一页</button>
      </nav>

      <div class="start-link">
        <router-link to="/exercise">开始训练</router-link>
      </div>
    </template>

    <section v-else-if="!busy && listErr" class="empty-state">
      <h3>训练历史暂时无法读取</h3>
      <p class="muted">读取失败不代表没有训练记录。</p>
      <button class="secondary" type="button" :disabled="busy" @click="load">重新加载</button>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import api, { errorMessage, getUser } from "../api/client";

const user = getUser();
const busy = ref(false);
const listErr = ref("");
const countErr = ref("");
const summaryErr = ref("");
const summary = ref(null);
const sessions = ref(null);
const page = ref(1);
const pageSize = 10;
const total = ref(0);
const allSessionTotal = ref(null);
const status = ref("");
const exerciseId = ref("");
const exerciseOptions = ref([]);
let requestId = 0;

const hasFilters = computed(() => Boolean(status.value || exerciseId.value));
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));

const statusName = (value) => ({ running: "未完成", finished: "已完成", cancelled: "已取消" }[value] || "状态未知");
const timeValue = (value) => {
  if (!value) return undefined;
  return value.endsWith("Z") || /[+-]\d{2}:?\d{2}$/.test(value) ? value : `${value}Z`;
};
function formatTime(value) {
  const normalized = timeValue(value);
  if (!normalized) return "时间未记录";
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? "时间未记录" : date.toLocaleString("zh-CN");
}

function assessmentStatus(session) {
  return session.analysis?.status || "unavailable";
}

function assessmentText(session) {
  const analysis = session.analysis;
  if (!analysis) return "尚无归档评估结果";
  if (analysis.status === "model") {
    return analysis.score == null ? "模型评估未返回有效分数" : `模型评估 · ${analysis.score} 分`;
  }
  if (analysis.status === "demo") return "演示/备用结果 · 不计入有效评分";
  return "评估暂不可用 · 不计入有效评分";
}

async function load() {
  const currentRequest = ++requestId;
  busy.value = true;
  listErr.value = "";
  countErr.value = "";
  summaryErr.value = "";

  const pageParams = {
    page: page.value,
    page_size: pageSize,
    status: status.value,
    exercise_id: exerciseId.value,
  };
  const pageUrl = `/users/${user.id}/sessions/page`;
  const historyRequests = [api.get(pageUrl, { params: pageParams })];
  if (hasFilters.value) {
    historyRequests.push(api.get(pageUrl, { params: { page: 1, page_size: 1 } }));
  }

  const [historyResult, summaryResult] = await Promise.all([
    Promise.allSettled(historyRequests),
    api.get(`/users/${user.id}/kb/summary`).then(
      (response) => ({ status: "fulfilled", value: response }),
      (reason) => ({ status: "rejected", reason }),
    ),
  ]);
  if (currentRequest !== requestId) return;

  const pageResult = historyResult[0];
  if (pageResult.status === "fulfilled") {
    const data = pageResult.value.data;
    sessions.value = data.items;
    total.value = data.total;
    exerciseOptions.value = data.exercises || [];
    if (!hasFilters.value) {
      allSessionTotal.value = data.total;
    } else {
      const countResult = historyResult[1];
      if (countResult.status === "fulfilled") {
        allSessionTotal.value = countResult.value.data.total;
      } else {
        allSessionTotal.value = null;
        countErr.value = errorMessage(countResult.reason, "全部记录数量读取失败。");
      }
    }
  } else {
    listErr.value = errorMessage(pageResult.reason, "训练历史读取失败，请检查连接后重试。");
  }

  if (summaryResult.status === "fulfilled") {
    summary.value = summaryResult.value.data;
  } else {
    summaryErr.value = errorMessage(summaryResult.reason, "训练统计读取失败。");
  }
  busy.value = false;
}

function resetPage() {
  page.value = 1;
  load();
}

function changePage(delta) {
  page.value += delta;
  load();
}

function clearFilters() {
  status.value = "";
  exerciseId.value = "";
  page.value = 1;
  load();
}

onMounted(load);
</script>

<style scoped>
.history-page { min-width: 0; }
.history-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.history-header h2 { margin-top: 0; }
.history-header p { margin-bottom: 0; }
.summary-section { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 16px 0 20px; }
.summary-stat { min-width: 0; padding: 12px; border: 1px solid var(--line); border-radius: 6px; }
.summary-stat span, .summary-stat strong { display: block; }
.summary-stat span { color: var(--muted); font-size: 13px; }
.summary-stat strong { margin-top: 4px; color: var(--accent); font-size: 20px; }
.summary-caption { grid-column: 1 / -1; margin: 0; font-size: 13px; }
.notice { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin: 12px 0; padding: 10px 12px; border-radius: 6px; }
.notice-actions { display: flex; flex: 0 0 auto; flex-wrap: wrap; gap: 8px; }
.error-notice { color: var(--bad); background: #fff5f4; }
.muted-notice { background: #f3f6f4; }
.history-controls { display: flex; flex-wrap: wrap; align-items: end; gap: 12px; margin: 20px 0 12px; }
.history-controls label { display: grid; gap: 4px; font-size: 14px; }
.history-controls select { min-width: 150px; }
.result-count { margin-left: auto; padding: 8px 0; }
.history-list { border-top: 1px solid var(--line); }
.history-entry { display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 16px 4px; border-bottom: 1px solid var(--line); }
.entry-main { min-width: 0; overflow-wrap: anywhere; }
.entry-title-line { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.entry-title-line h3 { margin: 0; font-size: 17px; }
.status-label { display: inline-flex; align-items: center; min-height: 24px; padding: 2px 8px; border-radius: 4px; background: #e7f3ed; color: #1e6e50; font-size: 12px; }
.status-running { background: #fff4df; color: #8a4d0f; }
.status-cancelled { background: #eef1f0; color: #53615a; }
.entry-time { display: block; margin-top: 6px; font-size: 14px; }
.assessment-line { margin: 8px 0 0; font-size: 14px; }
.assessment-demo, .assessment-unavailable { color: var(--warn); }
.assessment-model { color: var(--accent); }
.history-note { margin: 6px 0 0; font-size: 13px; }
.session-id { display: block; margin-top: 6px; font-size: 12px; }
.entry-actions { display: flex; flex: 0 0 auto; align-items: center; gap: 8px; }
.action-link { display: inline-flex; align-items: center; justify-content: center; min-height: 40px; padding: 8px 12px; border-radius: 6px; background: var(--accent); color: #fff; }
.empty-state { padding: 28px 12px; text-align: center; }
.empty-state h3 { margin: 0 0 8px; font-size: 18px; }
.empty-state p { margin: 0 0 16px; }
.pagination { display: flex; align-items: center; justify-content: center; gap: 14px; padding: 18px 0 8px; }
.start-link { margin-top: 16px; text-align: right; }
.start-link a { text-decoration: underline; text-underline-offset: 3px; }
button, select { min-height: 40px; }
@media (max-width: 600px) {
  .history-header { align-items: center; }
  .summary-section { grid-template-columns: 1fr 1fr; }
  .summary-stat:last-of-type { grid-column: 1 / -1; }
  .history-controls { align-items: stretch; }
  .history-controls label, .history-controls select { width: 100%; }
  .result-count { width: 100%; margin: 0; padding: 0; }
  .history-entry { align-items: flex-start; flex-direction: column; gap: 12px; }
  .entry-actions, .action-link { width: 100%; }
  .action-link { min-height: 44px; }
  .notice { align-items: flex-start; flex-direction: column; }
  .notice-actions { width: 100%; }
  .pagination { justify-content: space-between; gap: 8px; }
  .pagination button { min-height: 44px; }
}
</style>
