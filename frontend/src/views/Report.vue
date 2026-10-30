<template>
  <div class="card">
    <h2>运动后报告 · Video CoT</h2>
    <div class="row">
      <input v-model="sessionId" placeholder="session_id" />
      <button @click="load">加载报告</button>
      <router-link to="/prescription"><button class="secondary">查看已更新处方</button></router-link>
    </div>
    <p v-if="err" class="err">{{ err }}</p>
    <div v-if="data" class="grid-2" style="margin-top:16px">
      <div>
        <h3>{{ data.session?.exercise_name || "动作" }}</h3>
        <p class="muted">视频：{{ data.session?.video_path }}</p>
        <p class="ok" v-if="poseLine">{{ poseLine }}</p>
        <div class="stat">
          <span>完成度</span>
          <b>{{ cot.score ?? "—" }}</b>
        </div>
        <div class="score-bar"><i :style="{ width: (cot.score || 0) + '%' }"></i></div>
        <p>错误类型：<span class="tag" v-for="e in cot.errors || []" :key="e">{{ e }}</span></p>
        <p v-if="cot.advice" class="ok">建议：{{ cot.advice }}</p>
        <h3>五任务摘要</h3>
        <p>识别：{{ tasks.recognize?.class || "—" }}</p>
        <p>定位：{{ (tasks.localize?.segments || []).length }} 个片段</p>
        <p>评估分：{{ tasks.assess?.score ?? "—" }}</p>
        <p>描述：{{ tasks.describe?.description || "—" }}</p>
      </div>
      <div>
        <h3>CoT 分步推理</h3>
        <ol>
          <li v-for="(s, i) in cot.steps || []" :key="i">{{ s }}</li>
        </ol>
        <p class="muted">
          CoT 文字当前为可替换推理桩；姿态序列来自上方估计器（真算）。处方已按报告自动微调。
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import api from "../api/client";

const sessionId = ref(localStorage.getItem("ah_last_session") || "");
const data = ref(null);
const err = ref("");
const cot = computed(() => data.value?.report?.cot || {});
const tasks = computed(() => data.value?.report?.tasks || {});
const poseSummary = computed(() => data.value?.session?.pose_summary || {});
const poseLine = computed(() => {
  const p = poseSummary.value;
  if (!p || typeof p !== "object") return "";
  const name = p.estimator?.name || p.estimator?.family || "";
  const n =
    p.sequences?.coco17?.frames?.length ||
    p.raw?.frame_count ||
    0;
  if (!name && !n) return "";
  const runtime = p.estimator?.runtime ? ` · ${p.estimator.runtime}` : "";
  return `姿态：${name || "unknown"}${runtime} · COCO-17 ${n} 帧（真估计）`;
});

async function load() {
  err.value = "";
  if (!sessionId.value) {
    err.value = "还没有会话，请先去运动页或总览一键演示。";
    return;
  }
  try {
    data.value = (await api.get(`/reports/${sessionId.value}`)).data;
  } catch (e) {
    err.value = e?.response?.data?.detail || "报告不存在";
  }
}

onMounted(load);
</script>
