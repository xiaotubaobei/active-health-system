<template>
  <div class="card">
    <h2>运动后报告</h2>
    <div class="row">
      <label>训练编号 <input v-model="sessionId" type="number" min="1" placeholder="如 1" /></label>
      <button @click="load" :disabled="busy">{{ busy ? "正在加载…" : "加载报告" }}</button>
      <router-link to="/history"><button class="secondary">训练历史</button></router-link>
      <router-link to="/prescription"><button class="secondary">查看当前处方</button></router-link>
    </div>
    <p v-if="err" class="err" role="alert">{{ err }}</p>
    <div v-if="data" style="margin-top:16px">
      <h3>{{ data.session?.exercise_name || "动作" }} · 训练 #{{ data.session?.id }}</h3>
      <p class="muted">视频：{{ data.session?.video_path || "未保存视频" }}</p>
      <p v-if="poseLine">{{ poseLine }}</p>
      <span class="tag" :class="{ gray: analysis.status !== 'model' }">{{ analysis.status === 'model' ? "模型评估" : analysis.status === 'demo' ? "演示 / 备用结果" : "评估未完成" }}</span>
      <p class="muted">{{ analysis.message }}。本次训练不会自动调整处方。</p>
      <div class="stat"><span>模型评估分</span><b>{{ analysis.score ?? "暂无有效评分" }}</b></div>
      <template v-if="analysis.score != null">
        <div class="score-bar"><i :style="{ width: analysis.score + '%' }"></i></div>
        <p>错误类型：<span class="tag" v-for="e in cot.errors || []" :key="e">{{ e }}</span><span v-if="!cot.errors?.length">未返回错误项</span></p>
        <p v-if="cot.advice">模型建议：{{ cot.advice }}</p>
        <h3>分析步骤</h3>
        <ol><li v-for="(step, i) in cot.steps || []" :key="i">{{ step }}</li></ol>
      </template>
      <h3>动作计数与区间</h3>
      <template v-if="motion.status === 'ok'">
        <p>完成次数：{{ motion.rep_count ?? "未返回" }}</p>
        <p v-for="(interval, i) in motion.rep_intervals || []" :key="i">第 {{ i + 1 }} 次：{{ interval.start_sec }}–{{ interval.end_sec }} 秒</p>
      </template>
      <p v-else class="muted">{{ motion.error || motion.message || "本次尚无动作计数结果；不使用演示次数补齐。" }}</p>
      <details style="margin-top:16px">
        <summary>查看原始服务结果（可能含演示数据）</summary>
        <pre style="white-space:pre-wrap;overflow-wrap:anywhere">{{ JSON.stringify(data.report, null, 2) }}</pre>
      </details>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";
import api, { errorMessage } from "../api/client";

const route = useRoute();
const sessionId = ref("");
const data = ref(null);
const err = ref("");
const busy = ref(false);
let requestId = 0;
const cot = computed(() => data.value?.report?.cot || {});
const analysis = computed(() => data.value?.analysis || { status: "unavailable", score: null, message: "暂无有效模型评估" });
const pose = computed(() => data.value?.session?.pose_summary || {});
const motion = computed(() => pose.value.motion_analysis || {});
const poseLine = computed(() => {
  const p = pose.value;
  const n = p.sequences?.coco17?.frames?.length || p.raw?.frame_count || 0;
  if (!n) return "本次未保存有效姿态帧。";
  return `姿态记录：${p.estimator?.name || p.estimator?.family || p.source || "来源未标记"} · ${n} 帧`;
});
async function load() {
  const current = ++requestId;
  data.value = null;
  err.value = "";
  if (!Number.isInteger(Number(sessionId.value)) || Number(sessionId.value) <= 0) {
    err.value = "请选择训练历史中的报告，或输入有效训练编号。";
    busy.value = false;
    return;
  }
  busy.value = true;
  try {
    const response = await api.get(`/reports/${Number(sessionId.value)}`);
    if (current === requestId) data.value = response.data;
  } catch (error) {
    if (current === requestId) err.value = errorMessage(error, "报告读取失败，请稍后重试。");
  } finally { if (current === requestId) busy.value = false; }
}
watch(() => route.query.session_id, (value) => {
  sessionId.value = value || localStorage.getItem("ah_last_session") || "";
  load();
}, { immediate: true });
</script>
