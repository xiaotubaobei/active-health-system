<template>
  <div class="card">
    <h2>训练历史与个人知识库</h2>
    <p class="muted">训练完成后保存报告、姿态摘要与提示记录。演示和服务不可用时的备用结果不参与成绩统计。</p>
    <button class="secondary" @click="load" :disabled="busy">{{ busy ? "正在读取…" : "刷新记录" }}</button>
    <p v-if="err" class="err" role="alert">{{ err }}</p>
    <template v-if="summary">
      <div class="row" style="margin:16px 0">
        <div class="stat"><span>已完成训练</span><b>{{ summary.finished_sessions }}</b></div>
        <div class="stat"><span>归档记录</span><b>{{ summary.kb_entries }}</b></div>
        <div class="stat"><span>最近模型均分</span><b>{{ summary.avg_score_recent ?? "暂无" }}</b></div>
      </div>
      <p class="muted">均分范围：最近 20 条归档中，有效模型评估 {{ summary.scored_entries_recent }} 条。</p>
      <h3>训练记录</h3>
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
      <p v-if="!sessions.length" class="muted">当前筛选条件下没有训练记录，可切换条件或前往运动页开始训练。</p>
      <div v-for="session in sessions" :key="session.id" style="border-top:1px solid #e5e7eb;padding:14px 0">
        <strong>{{ session.exercise_name || session.exercise_id }}</strong>
        <span class="tag gray">{{ statusName(session.status) }}</span>
        <p class="muted">训练 #{{ session.id }} · {{ formatTime(session.finished_at || session.started_at) }}</p>
        <template v-if="session.analysis">
          <p>评估：{{ session.analysis.score == null ? "暂无有效模型评分" : `${session.analysis.score} 分` }}</p>
          <p>{{ session.history_note }}</p>
        </template>
        <router-link v-if="session.status === 'running'" :to="{ path: '/exercise', query: { session_id: session.id } }">继续本次训练</router-link>
        <router-link v-if="session.status === 'finished'" :to="{ path: '/report', query: { session_id: session.id } }">查看本次报告</router-link>
      </div>
      <div class="row" style="margin:12px 0">
        <button class="secondary" :disabled="busy || page <= 1" @click="changePage(-1)">上一页</button>
        <button class="secondary" :disabled="busy || page * pageSize >= total" @click="changePage(1)">下一页</button>
      </div>
      <router-link to="/exercise"><button>开始训练</button></router-link>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import api, { errorMessage, getUser } from "../api/client";

const user = getUser();
const busy = ref(false);
const err = ref("");
const summary = ref(null);
const sessions = ref([]);
const page = ref(1);
const pageSize = 10;
const total = ref(0);
const status = ref("");
const exerciseId = ref("");
const exerciseOptions = ref([]);
const statusName = (value) => ({ finished: "已完成", running: "未完成", cancelled: "已取消" }[value] || value);
function resetPage() { page.value = 1; load(); }
function changePage(delta) { page.value += delta; load(); }
const formatTime = (value) => value ? new Date(value.endsWith("Z") ? value : `${value}Z`).toLocaleString("zh-CN") : "时间未记录";
async function load() {
  busy.value = true;
  err.value = "";
  try {
    const [kb, history] = await Promise.all([
      api.get(`/users/${user.id}/kb/summary`), api.get(`/users/${user.id}/sessions/page`, { params: { page: page.value, page_size: pageSize, status: status.value, exercise_id: exerciseId.value } }),
    ]);
    summary.value = kb.data;
    sessions.value = history.data.items;
    total.value = history.data.total;
    exerciseOptions.value = history.data.exercises;
  } catch (error) { err.value = errorMessage(error, "记录读取失败，请稍后刷新。"); }
  finally { busy.value = false; }
}
onMounted(load);
</script>
