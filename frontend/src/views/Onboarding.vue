<template>
  <div class="card">
    <h2>首次测评与运动档案</h2>
    <p class="muted">填写个人资料和已有体测的项目得分，保存为首次基线，并生成一份模板处方供查看。</p>
    <p v-if="loading">正在读取档案…</p>
    <p v-if="err" class="err" role="alert">{{ err }}</p>
    <button v-if="!ready && !loading" @click="load">重新加载</button>
    <div v-if="done">
      <p class="ok">首次测评已完成。后续测评请进入「体适能评估」。</p>
      <p v-if="baseline">首次基线：{{ baseline.total_score }} 分（{{ levelName(baseline.level) }}）</p>
      <p v-else class="muted">此演示账号没有首次基线记录。</p>
      <router-link to="/fitness"><button>后续体适能评估</button></router-link>
      <router-link to="/prescription"><button class="secondary">查看运动处方</button></router-link>
    </div>
    <form v-else-if="ready" @submit.prevent="submit">
      <div class="row" style="margin:12px 0">
        <label>年龄组 <select v-model="form.age_group"><option value="youth">青少年</option><option value="middle_age">中年</option><option value="elder">老年</option></select></label>
        <label>身高（厘米）<input v-model.number="form.height_cm" type="number" step="0.1" min="1" max="300" required /></label>
        <label>体重（公斤）<input v-model.number="form.weight_kg" type="number" step="0.1" min="1" max="700" required /></label>
      </div>
      <div class="row" style="margin:12px 0">
        <label>运动目标 <select v-model="form.goal"><option value="fitness">日常健身</option><option value="medical">健康管理（需专业人员审核）</option></select></label>
        <label>慢病标签（选填，用逗号分隔）<input v-model="tags" placeholder="如 hypertension, diabetes" /></label>
      </div>
      <h3>{{ current?.name }}</h3>
      <p class="muted">请填写体测换算后的 0–100 分，不是体重、秒数或次数。没有测量的项目请先完成测量；系统不会自动补分。</p>
      <div v-for="item in current?.items || []" :key="item.key" class="row" style="margin:8px 0">
        <label :for="`score-${item.key}`" style="width:200px">{{ item.name }}（权重 {{ item.weight }}）</label>
        <input :id="`score-${item.key}`" v-model.number="scores[item.key]" type="number" min="0" max="100" step="0.1" required placeholder="0–100 分" />
      </div>
      <p><label><input v-model="consent" type="checkbox" required /> 我同意将上述资料、测评与训练记录用于本系统的个人档案；本系统提供运动健康建议，不构成医疗诊断或治疗。</label></p>
      <button type="submit" :disabled="busy || !current">{{ busy ? "正在保存…" : "保存首次测评并生成模板处方" }}</button>
    </form>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import api, { errorMessage, getUser, setUser } from "../api/client";

const router = useRouter();
const user = getUser();
const form = reactive({ age_group: user.age_group || "middle_age", height_cm: user.height_cm || 170, weight_kg: user.weight_kg || 65, goal: user.goal || "fitness" });
const tags = ref((user.chronic_tags || []).join(", "));
const consent = ref(false);
const scores = reactive({});
const scales = ref([]);
const done = ref(false);
const baseline = ref(null);
const loading = ref(false);
const ready = ref(false);
const busy = ref(false);
const err = ref("");
const current = computed(() => scales.value.find((s) => s.id === (form.age_group === "youth" ? "youth" : "middle_elder")));
watch(current, () => { for (const key of Object.keys(scores)) delete scores[key]; });
const levelName = (level) => ({ excellent: "优秀", good: "良好", average: "一般", poor: "较弱" }[level] || level);

async function load() {
  loading.value = true;
  ready.value = false;
  err.value = "";
  try {
    const [status, catalog] = await Promise.all([
      api.get("/onboarding/status", { params: { user_id: user.id } }), api.get("/fitness/scales"),
    ]);
    done.value = status.data.onboarding_done;
    baseline.value = status.data.baseline;
    scales.value = catalog.data;
    setUser({ ...getUser(), onboarding_done: done.value, privacy_consent: status.data.privacy_consent });
    ready.value = true;
  } catch (error) {
    err.value = errorMessage(error, "无法读取测评状态，请确认后端已启动后重新加载。");
  } finally { loading.value = false; }
}

async function submit() {
  err.value = "";
  const payload = {};
  for (const item of current.value?.items || []) {
    const value = scores[item.key];
    if (value === "" || value == null || !Number.isFinite(Number(value)) || value < 0 || value > 100) {
      err.value = `请填写「${item.name}」的有效分数（0–100）`;
      return;
    }
    payload[item.key] = Number(value);
  }
  if (!consent.value || !current.value) return;
  busy.value = true;
  try {
    const { data } = await api.post("/onboarding/complete", {
      ...form, user_id: user.id, scale_id: current.value.id, scores: payload,
      chronic_tags: tags.value.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
      privacy_consent: true, generate_prescription: true,
    });
    setUser(data.user);
    await router.push("/prescription");
  } catch (error) { err.value = errorMessage(error, "保存失败，请检查资料和分数后重试。"); }
  finally { busy.value = false; }
}
onMounted(load);
</script>
