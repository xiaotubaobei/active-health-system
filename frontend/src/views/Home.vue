<template>
  <div class="home-dashboard">
    <header class="card home-hero">
      <div>
        <p class="home-kicker">你好，{{ user?.username || "训练伙伴" }}</p>
        <h2>我的训练</h2>
        <p class="home-status">{{ homeStatusText }}</p>
      </div>
      <button class="secondary" @click="loadHomeData" :disabled="homeLoading">
        {{ homeLoading ? "正在加载…" : "重新加载" }}
      </button>
    </header>

    <section class="card" aria-labelledby="current-plan-title">
      <div class="section-heading">
        <div>
          <p class="section-kicker">训练安排</p>
          <h3 id="current-plan-title">当前训练计划</h3>
        </div>
        <span v-if="planState.status === 'success'" class="tag">
          {{ planStatusName(planState.data.status) }}
        </span>
      </div>

      <p v-if="planState.status === 'loading'" class="muted">正在读取训练计划…</p>
      <div v-else-if="planState.status === 'empty'" class="empty-state">
        <strong>还没有训练计划</strong>
        <p class="muted">到训练计划页查看可用方案；暂未匹配时按页面提示补充资料。</p>
        <router-link to="/prescription" class="action-button secondary">前往训练计划</router-link>
      </div>
      <div v-else-if="planState.status === 'error'" class="error-state">
        <p class="err">训练计划暂时无法读取，请重新加载。</p>
        <button class="secondary" @click="loadHomeData" :disabled="homeLoading">重新加载</button>
      </div>
      <div v-else-if="planState.status === 'success'">
        <p class="plan-summary">
          <strong>第 {{ planState.data.version }} 版计划</strong>
          <span v-if="planState.data.frequency">{{ planState.data.frequency }}</span>
          <span v-if="planState.data.duration">每次 {{ planState.data.duration }}</span>
          <span v-if="planState.data.cycle">周期 {{ planState.data.cycle }}</span>
        </p>
        <p v-if="planState.data.mode || planState.data.intensity" class="muted">
          {{ [planState.data.mode, planState.data.intensity ? `强度：${planState.data.intensity}` : ""].filter(Boolean).join(" · ") }}
        </p>
        <div v-if="planState.data.exercises?.length" class="exercise-tags" aria-label="计划动作">
          <span v-for="exercise in planState.data.exercises" :key="exercise.id || exercise.name" class="tag gray">
            {{ exercise.name || "训练动作" }}
          </span>
        </div>
        <p v-else class="muted">计划中暂时没有可展示的训练动作。</p>
      </div>
    </section>

    <section class="card" aria-labelledby="overview-title">
      <div class="section-heading">
        <div>
          <p class="section-kicker">训练数据</p>
          <h3 id="overview-title">训练概况</h3>
        </div>
      </div>
      <div class="overview-grid">
        <div class="overview-item">
          <span>已完成训练</span>
          <strong v-if="summaryState.status === 'success'">{{ summaryState.data.finished_sessions }} 次</strong>
          <strong v-else-if="summaryState.status === 'error'">读取失败</strong>
          <strong v-else>—</strong>
          <small v-if="summaryState.status === 'loading'">正在读取</small>
          <small v-else-if="summaryState.status === 'error'">请重新加载</small>
          <small v-else>累计完成次数</small>
        </div>

        <div class="overview-item">
          <span>最近一次训练</span>
          <strong v-if="recentState.status === 'success'">{{ latestSession.exercise_name || "训练动作" }}</strong>
          <strong v-else-if="recentState.status === 'error'">读取失败</strong>
          <strong v-else-if="recentState.status === 'empty'">暂无记录</strong>
          <strong v-else>—</strong>
          <small v-if="recentState.status === 'success'">{{ formatTime(latestSession.finished_at || latestSession.started_at) }}</small>
          <small v-else-if="recentState.status === 'loading'">正在读取</small>
          <small v-else-if="recentState.status === 'error'">请重新加载</small>
          <small v-else>完成训练后会显示</small>
        </div>

        <div class="overview-item">
          <span>当前计划</span>
          <strong v-if="planState.status === 'success'">第 {{ planState.data.version }} 版</strong>
          <strong v-else-if="planState.status === 'error'">读取失败</strong>
          <strong v-else-if="planState.status === 'empty'">暂无计划</strong>
          <strong v-else>—</strong>
          <small v-if="planState.status === 'success'">{{ planStatusName(planState.data.status) }}</small>
          <small v-else-if="planState.status === 'loading'">正在读取</small>
          <small v-else-if="planState.status === 'error'">请重新加载</small>
          <small v-else>可前往训练计划生成</small>
        </div>
      </div>
    </section>

    <section class="card primary-actions" aria-labelledby="actions-title">
      <div>
        <p class="section-kicker">下一步</p>
        <h3 id="actions-title">开始你的训练</h3>
        <p v-if="runningState.status === 'success' && runningSession" class="muted">
          继续 {{ runningSession.exercise_name || "上次训练" }}，将使用原来的训练记录。
        </p>
        <p v-else-if="runningState.status === 'empty'" class="muted">当前没有未完成训练，可以开始一次新训练。</p>
        <p v-else-if="runningState.status === 'error'" class="err">训练状态读取失败，请重新加载。</p>
        <p v-else-if="runningState.status === 'success'" class="err">训练记录编号无效，请重新加载。</p>
        <p v-else class="muted">正在读取训练状态…</p>
      </div>
      <div class="action-group">
        <router-link
          v-if="runningState.status === 'success' && runningSession"
          class="action-button"
          :to="{ path: '/exercise', query: { session_id: runningSession.id } }"
        >
          继续上次训练
        </router-link>
        <router-link
          v-else-if="runningState.status === 'empty'"
          class="action-button"
          to="/exercise"
        >
          开始训练
        </router-link>
        <button v-else-if="runningState.status === 'loading'" disabled>正在读取训练状态…</button>
        <button v-else-if="runningState.status === 'success'" disabled>训练记录不可用</button>
        <button v-else class="secondary" @click="loadHomeData" :disabled="homeLoading">重新加载</button>

        <router-link
          v-if="latestFinishedSession"
          class="action-button secondary"
          :to="{ path: '/report', query: { session_id: latestFinishedSession.id } }"
        >
          查看最近报告
        </router-link>
        <button v-else-if="finishedState.status === 'loading'" class="secondary" disabled>正在读取最近报告…</button>
        <span v-else-if="finishedState.status === 'error'" class="action-error">最近报告读取失败，请重新加载</span>
      </div>
    </section>

    <section class="card" aria-labelledby="recent-title">
      <div class="section-heading">
        <div>
          <p class="section-kicker">训练记录</p>
          <h3 id="recent-title">最近训练</h3>
        </div>
        <router-link to="/history" class="text-link">查看全部记录</router-link>
      </div>

      <p v-if="recentState.status === 'loading'" class="muted">正在读取最近训练…</p>
      <div v-else-if="recentState.status === 'empty'" class="empty-state">
        <strong>还没有训练记录</strong>
        <p class="muted">完成第一次训练后会显示在这里。</p>
      </div>
      <div v-else-if="recentState.status === 'error'" class="error-state">
        <p class="err">最近训练暂时无法读取，请重新加载。</p>
        <button class="secondary" @click="loadHomeData" :disabled="homeLoading">重新加载</button>
      </div>
      <ul v-else-if="recentState.status === 'success'" class="recent-list">
        <li v-for="item in recentState.data" :key="item.id">
          <div>
            <strong>{{ item.exercise_name || "训练动作" }}</strong>
            <p class="muted">{{ formatTime(item.finished_at || item.started_at) }}</p>
          </div>
          <div class="record-meta">
            <span class="tag" :class="{ gray: item.status !== 'finished' }">{{ sessionStatusName(item.status) }}</span>
            <small class="muted">记录 #{{ item.id }}</small>
          </div>
        </li>
      </ul>
    </section>

    <details class="card demo-area">
      <summary>
        <span>
          <strong>体验演示数据</strong>
          <small>了解训练报告的大致呈现方式</small>
        </span>
      </summary>
      <div class="demo-content">
        <p class="muted">演示数据仅用于体验页面流程，不代表你的真实训练结果，也不会作为训练成绩；演示会生成训练记录，累计次数可能包含体验记录。</p>
        <button class="secondary" @click="runDemo" :disabled="busy">
          {{ busy ? "演示生成中…" : "生成演示训练报告" }}
        </button>
        <p v-if="msg" class="ok">{{ msg }}</p>
        <p v-if="err" class="err">{{ err }}</p>
      </div>
    </details>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import api, { errorMessage, getUser } from "../api/client";

const user = ref(getUser());
const router = useRouter();
const busy = ref(false);
const msg = ref("");
const err = ref("");
const makeState = () => reactive({ status: "loading", data: null, error: "" });
const planState = makeState();
const summaryState = makeState();
const recentState = makeState();
const runningState = makeState();
const finishedState = makeState();
let loadSequence = 0;

const homeLoading = computed(() =>
  [planState, summaryState, recentState, runningState, finishedState].some((state) => state.status === "loading"),
);

const latestSession = computed(() =>
  recentState.status === "success" ? recentState.data?.[0] || null : null,
);

function validSessionId(value) {
  const id = Number(value);
  return Number.isInteger(id) && id > 0;
}

const runningSession = computed(() => {
  if (runningState.status !== "success" || !validSessionId(runningState.data?.id)) return null;
  return runningState.data;
});

const latestFinishedSession = computed(() => {
  if (finishedState.status !== "success" || !validSessionId(finishedState.data?.id)) return null;
  return finishedState.data;
});

const homeStatusText = computed(() => {
  if (runningState.status === "loading") return "正在读取你的训练状态…";
  if (runningState.status === "error") return "训练状态暂时无法读取，请重新加载。";
  if (runningState.status === "success") return "你有未完成的训练，可以从上次记录继续。";
  if (planState.status === "loading") return "正在读取你的训练安排…";
  if (planState.status === "error") return "训练计划暂时无法读取，请重新加载。";
  if (planState.status === "empty") return "还没有训练计划，可先查看计划页的匹配说明。";
  return "可以开始训练。";
});

const planStatusName = (status) => ({
  clinical_intake: "资料准备中",
  fitness_assessed: "已完成评估",
  pre_prescription: "计划待确认",
  monitoring: "训练观察中",
  formal_prescription: "计划已确认",
  implementing: "训练进行中",
  feedback: "等待训练反馈",
}[status] || "计划已生成");

function resetState(state) {
  state.status = "loading";
  state.data = null;
  state.error = "";
}

function failState(state, error, fallback) {
  state.status = "error";
  state.data = null;
  state.error = errorMessage(error, fallback);
}

function isCurrentLoad(sequence, userId) {
  return sequence === loadSequence && String(getUser()?.id ?? "") === String(userId);
}

async function loadPlan(sequence, userId) {
  try {
    const { data } = await api.get("/prescriptions/current", { params: { user_id: userId } });
    if (!isCurrentLoad(sequence, userId)) return;
    if (!data || typeof data !== "object") throw new Error("训练计划返回格式不正确");
    planState.status = "success";
    planState.data = data;
  } catch (error) {
    if (!isCurrentLoad(sequence, userId)) return;
    const detail = error?.response?.data?.detail;
    if (error?.response?.status === 404 && typeof detail === "string" && detail.includes("尚无处方")) {
      planState.status = "empty";
      planState.data = null;
      return;
    }
    failState(planState, error, error?.message || "请检查网络后重试");
  }
}

async function loadSummary(sequence, userId) {
  try {
    const { data } = await api.get(`/users/${userId}/kb/summary`);
    if (!isCurrentLoad(sequence, userId)) return;
    if (!Number.isInteger(data?.finished_sessions) || data.finished_sessions < 0) {
      throw new Error("训练统计返回格式不正确");
    }
    summaryState.status = "success";
    summaryState.data = data;
  } catch (error) {
    if (!isCurrentLoad(sequence, userId)) return;
    failState(summaryState, error, error?.message || "请检查网络后重试");
  }
}

async function loadRecent(sequence, userId) {
  try {
    const { data } = await api.get(`/users/${userId}/sessions/page`, {
      params: { page: 1, page_size: 3 },
    });
    if (!isCurrentLoad(sequence, userId)) return;
    if (!Array.isArray(data?.items)) throw new Error("最近训练返回格式不正确");
    recentState.data = data.items.slice(0, 3);
    recentState.status = recentState.data.length ? "success" : "empty";
  } catch (error) {
    if (!isCurrentLoad(sequence, userId)) return;
    failState(recentState, error, error?.message || "请检查网络后重试");
  }
}

async function loadRunning(sequence, userId) {
  try {
    const { data } = await api.get(`/users/${userId}/sessions/page`, {
      params: { status: "running", page: 1, page_size: 1 },
    });
    if (!isCurrentLoad(sequence, userId)) return;
    if (!Array.isArray(data?.items)) throw new Error("未完成训练返回格式不正确");
    runningState.data = data.items[0] || null;
    runningState.status = runningState.data ? "success" : "empty";
  } catch (error) {
    if (!isCurrentLoad(sequence, userId)) return;
    failState(runningState, error, error?.message || "请检查网络后重试");
  }
}

async function loadFinished(sequence, userId) {
  try {
    const { data } = await api.get(`/users/${userId}/sessions/page`, { params: { status: "finished", page: 1, page_size: 1 } });
    if (!isCurrentLoad(sequence, userId)) return;
    if (!Array.isArray(data?.items)) throw new Error("报告列表返回格式不正确");
    finishedState.data = data.items[0] || null;
    finishedState.status = finishedState.data ? "success" : "empty";
  } catch (error) {
    if (isCurrentLoad(sequence, userId)) failState(finishedState, error, "最近报告读取失败");
  }
}

async function loadHomeData() {
  const sequence = ++loadSequence;
  const currentUser = getUser();
  user.value = currentUser;
  [planState, summaryState, recentState, runningState, finishedState].forEach(resetState);

  if (!currentUser?.id) {
    const loginError = new Error("登录信息已失效，请重新登录");
    [planState, summaryState, recentState, runningState, finishedState].forEach((state) =>
      failState(state, loginError, loginError.message),
    );
    return;
  }

  const userId = currentUser.id;
  await Promise.all([
    loadPlan(sequence, userId),
    loadSummary(sequence, userId),
    loadRecent(sequence, userId),
    loadRunning(sequence, userId),
    loadFinished(sequence, userId),
  ]);
}

const sessionStatusName = (status) => ({
  running: "未完成",
  finished: "已完成",
  cancelled: "已取消",
}[status] || "状态待确认");

function formatTime(value) {
  if (!value) return "时间未知";
  const date = new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(value) ? value : `${value}Z`);
  return Number.isNaN(date.getTime()) ? "时间未知" : date.toLocaleString("zh-CN");
}

onMounted(loadHomeData);

async function runDemo() {
  busy.value = true;
  msg.value = "";
  err.value = "";
  try {
    const { data } = await api.post("/demo/run-loop", {
      user_id: user.value.id,
      exercise_id: "squat",
      exercise_name: "深蹲",
    });
    localStorage.setItem("ah_last_session", String(data.session_id));
    msg.value = data.message;
    router.push({ path: "/report", query: { session_id: data.session_id } });
  } catch (e) {
    err.value = e?.response?.data?.detail || "演示暂时无法运行，请确认系统服务已启动";
  } finally {
    busy.value = false;
  }
}
</script>

<style scoped>
.home-dashboard { max-width: 960px; }
.home-hero,
.section-heading,
.primary-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}
.home-hero h2,
.section-heading h3,
.primary-actions h3 { margin: 0; }
.home-kicker,
.section-kicker {
  margin: 0 0 5px;
  color: var(--accent);
  font-size: 13px;
  font-weight: 700;
}
.home-status { margin: 8px 0 0; color: var(--muted); }
.section-heading { margin-bottom: 16px; }
.plan-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 18px;
}
.exercise-tags { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.overview-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.overview-item {
  min-width: 0;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #f8fbf9;
}
.overview-item span,
.overview-item small { display: block; color: var(--muted); }
.overview-item strong { display: block; margin: 8px 0 4px; font-size: 20px; overflow-wrap: anywhere; }
.primary-actions { align-items: flex-end; }
.action-group { display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 12px; }
.action-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--accent);
  color: white;
  font-weight: 600;
}
.action-button.secondary { background: #4a6358; }
.action-error { color: var(--bad); font-size: 14px; }
.recent-list { list-style: none; margin: 0; padding: 0; }
.recent-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 0;
  border-top: 1px solid var(--line);
}
.recent-list li:first-child { border-top: 0; }
.recent-list p { margin: 5px 0 0; }
.record-meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.empty-state p,
.error-state p { margin: 8px 0 12px; }
.text-link { color: var(--accent); font-weight: 600; }
.demo-area { color: inherit; }
.demo-area summary { cursor: pointer; list-style-position: outside; }
.demo-area summary span { display: inline-flex; flex-direction: column; gap: 4px; margin-left: 6px; }
.demo-area summary small { color: var(--muted); font-weight: 400; }
.demo-content { margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--line); }
@media (max-width: 720px) {
  .home-hero,
  .primary-actions { align-items: flex-start; flex-direction: column; }
  .overview-grid { grid-template-columns: 1fr; }
  .recent-list li { align-items: flex-start; }
}
</style>
