<template>
  <div class="card">
    <h2>首次测评与运动档案</h2>
    <p class="muted">填写个人资料和已有体测的项目得分，保存为首次基线，并生成一份模板处方供查看。</p>
    <p v-if="loading">正在读取档案…</p>
    <p v-if="err" class="err" role="alert">{{ err }}</p>
    <button v-if="!ready && !loading" @click="load">重新加载</button>
    <div v-if="done">
      <p class="ok">首次测评已完成。后续测评请进入「体适能评估」。</p>
      <p v-if="baseline">首次录入分数汇总：{{ baseline.total_score }} 分（试验性加权汇总，不代表体适能达标）</p>
      <p v-else class="muted">此演示账号没有首次基线记录。</p>
      <router-link to="/fitness"><button>后续体适能评估</button></router-link>
      <router-link to="/prescription"><button class="secondary">查看运动处方</button></router-link>
    </div>
    <form v-else-if="ready" @submit.prevent="submit">
      <div class="row" style="margin:12px 0">
        <label>年龄组 <select v-model="form.age_group" required><option value="" disabled>请选择</option><option value="youth">青少年</option><option value="middle_age">中年</option><option value="elder">老年</option></select></label>
        <label>身高（厘米）<input v-model.number="form.height_cm" type="number" step="0.1" min="1" max="300" required /></label>
        <label>体重（公斤）<input v-model.number="form.weight_kg" type="number" step="0.1" min="1" max="700" required /></label>
      </div>
      <div class="row" style="margin:12px 0">
        <label>运动目标 <select v-model="form.goal" required><option value="" disabled>请选择</option><option value="fitness">日常健身</option><option value="medical">健康管理（需专业人员审核）</option></select></label>
        <label>慢病标签（选填，用逗号分隔）<input v-model="tags" placeholder="如 hypertension, diabetes" /></label>
      </div>
      <h3>{{ current?.name }}</h3>
      <p class="muted">身高、体重请填写本人实际测量值。下方仅供录入已有的 0–100 换算分，不是体重、秒数或次数。当前尚未提供原始成绩换算标准；没有已换算成绩时请勿估填。</p>
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
// 注册时的历史占位值不是用户确认过的测量值，首次填写必须由本人输入。
const form = reactive({ age_group: "", height_cm: "", weight_kg: "", goal: "" });
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
const current = computed(() => form.age_group ? scales.value.find((s) => s.id === (form.age_group === "youth" ? "youth" : "middle_elder")) : null);
watch(current, () => { for (const key of Object.keys(scores)) delete scores[key]; });

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
  if (busy.value) return;
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
