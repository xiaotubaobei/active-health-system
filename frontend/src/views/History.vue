<template>
  <div class="card">
    <h2>训练记录</h2>
    <p class="muted">在这里查看每次训练的时间、完成情况和训练报告。</p>
    <button class="secondary" @click="load" :disabled="busy">{{ busy ? "正在读取…" : "刷新记录" }}</button>
    <p v-if="err" class="err" role="alert">{{ err }}</p>
    <p v-if="summaryErr" class="err" role="alert">{{ summaryErr }}</p>
    <template v-if="summary">
      <div class="row" style="margin:16px 0">
        <div class="stat"><span>已完成训练</span><b>{{ summary.finished_sessions }}</b></div>
        <div class="stat"><span>报告记录</span><b>{{ summary.kb_entries }}</b></div>
        <div class="stat"><span>最近有效动作平均分</span><b>{{ summary.avg_score_recent ?? "暂无" }}</b></div>
      </div>
      <p class="muted">最近 20 条训练记录中，有 {{ summary.scored_entries_recent }} 条包含有效动作分析。</p>
    </template>
      <h3>全部记录</h3>
      <div class="row" style="margin-bottom:12px">
        <label>状态 <select v-model="status" @change="resetPage" :disabled="busy">
          <option value="">全部状态</option><option value="running">未完成</option>
          <option value="finished">已完成</option><option value="cancelled">已取消</option>
        </select></label>
        <label>动作 <select v-model="exerciseId" @change="resetPage" :disabled="busy">
          <option value="">全部动作</option><option v-for="e in exerciseOptions" :key="e.id" :value="e.id">{{ e.name }}</option>
        </select></label>
        <span class="muted">共 {{ total }} 条 · 第 {{ page }} / {{ Math.max(1, Math.ceil(total / pageSize)) }} 页</span>
      </div>
      <p v-if="busy" class="muted" role="status">正在读取训练记录…</p>
      <p v-else-if="!err && !sessions.length" class="muted">当前筛选条件下没有训练记录，可以更换条件或开始一次训练。</p>
      <div v-for="session in sessions" :key="session.id" style="border-top:1px solid #e5e7eb;padding:14px 0">
        <strong>{{ session.exercise_name || session.exercise_id }}</strong>
        <span class="tag gray">{{ statusName(session.status) }}</span>
        <p class="muted">训练 #{{ session.id }} · {{ formatTime(session.finished_at || session.started_at) }}</p>
        <template v-if="session.analysis">
          <p>动作分析：{{ session.analysis.score == null ? "暂无有效评分" : `${session.analysis.score} 分` }}</p>
          <p>{{ friendlyHistoryNote(session.history_note) }}</p>
        </template>
        <router-link v-if="session.status === 'running'" :to="{ path: '/exercise', query: { session_id: session.id } }">继续本次训练</router-link>
        <router-link v-if="session.status === 'finished'" :to="{ path: '/report', query: { session_id: session.id } }">查看本次报告 / 填写反馈</router-link>
      </div>
      <div class="row" style="margin:12px 0">
        <button class="secondary" :disabled="busy || page <= 1" @click="changePage(-1)">上一页</button>
        <button class="secondary" :disabled="busy || page * pageSize >= total" @click="changePage(1)">下一页</button>
      </div>
      <router-link class="primary-link" to="/exercise">开始训练</router-link>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import api, { errorMessage, getUser } from "../api/client";

const user = getUser();
const busy = ref(false);
const err = ref("");
const summary = ref(null);
const summaryErr = ref("");
let loadSequence = 0;
const sessions = ref([]);
const page = ref(1);
const pageSize = 10;
const total = ref(0);
const status = ref("");
const exerciseId = ref("");
const exerciseOptions = ref([]);
const statusName = (value) => ({ finished: "已完成", running: "未完成", cancelled: "已取消" }[value] || value);
const friendlyHistoryNote = (value) => (value || "")
  .replaceAll("有效模型评估", "有效动作分析")
  .replaceAll("模型评估", "动作分析")
  .replaceAll("已写入个人运动档案", "已保存到训练记录")
  .replaceAll("训练已归档", "训练记录已保存")
  .replaceAll("错误点", "动作问题");
function resetPage() { page.value = 1; load(); }
function changePage(delta) { page.value += delta; load(); }
const formatTime = (value) => value ? new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(value) ? value : `${value}Z`).toLocaleString("zh-CN") : "时间未记录";
async function load() {
  const current = ++loadSequence;
  busy.value = true;
  err.value = "";
  summaryErr.value = "";
  sessions.value = [];
  summary.value = null;
  total.value = 0;
  await Promise.all([
    (async () => {
      try {
        const { data } = await api.get(`/users/${user.id}/kb/summary`);
        if (current === loadSequence) summary.value = data;
      } catch (error) {
        if (current === loadSequence) summaryErr.value = errorMessage(error, "统计读取失败，仍可查看下方训练记录。");
      }
    })(),
    (async () => {
      try {
        const { data } = await api.get(`/users/${user.id}/sessions/page`, { params: { page: page.value, page_size: pageSize, status: status.value, exercise_id: exerciseId.value } });
        if (current !== loadSequence) return;
        if (!Array.isArray(data.items)) throw new Error("训练记录格式不正确");
        sessions.value = data.items;
        total.value = data.total;
        exerciseOptions.value = data.exercises || [];
      } catch (error) {
        if (current === loadSequence) err.value = errorMessage(error, "记录读取失败，请稍后刷新。");
      }
    })(),
  ]);
  if (current === loadSequence) busy.value = false;
}
onMounted(load);
</script>

<style scoped>
.primary-link {
  display: inline-block;
  padding: 8px 12px;
  border-radius: 6px;
  background: var(--accent);
  color: #fff;
  text-decoration: none;
}
</style>
