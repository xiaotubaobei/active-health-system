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
      <h3>最近训练（最多 50 次）</h3>
      <p v-if="!sessions.length" class="muted">还没有训练记录，完成首次测评后可前往运动页开始训练。</p>
      <div v-for="session in sessions" :key="session.id" style="border-top:1px solid #e5e7eb;padding:14px 0">
        <strong>{{ session.exercise_name || session.exercise_id }}</strong>
        <span class="tag gray">{{ session.status === "finished" ? "已完成" : "未完成" }}</span>
        <p class="muted">训练 #{{ session.id }} · {{ formatTime(session.finished_at || session.started_at) }}</p>
        <template v-if="entryFor(session.id)">
          <p>评估：{{ entryFor(session.id).score == null ? "暂无有效模型评分" : `${entryFor(session.id).score} 分` }}</p>
          <p>{{ entryFor(session.id).history_note }}</p>
        </template>
        <router-link v-if="session.status === 'finished'" :to="{ path: '/report', query: { session_id: session.id } }">查看本次报告</router-link>
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
const entryFor = (id) => summary.value?.entries?.find((entry) => entry.session_id === id);
const formatTime = (value) => value ? new Date(value.endsWith("Z") ? value : `${value}Z`).toLocaleString("zh-CN") : "时间未记录";
async function load() {
  busy.value = true;
  err.value = "";
  try {
    const [kb, history] = await Promise.all([
      api.get(`/users/${user.id}/kb/summary`), api.get(`/users/${user.id}/sessions`),
    ]);
    summary.value = kb.data;
    sessions.value = history.data;
  } catch (error) { err.value = errorMessage(error, "记录读取失败，请稍后刷新。"); }
  finally { busy.value = false; }
}
onMounted(load);
</script>
