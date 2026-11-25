<template>
  <div class="card">
    <h2>运动处方</h2>
    <p class="muted">系统当前按年龄组和标签选择模板，尚未根据个人测评、运动限制和训练反馈制定运动量。模板中的强度、频次与进阶安排需要结合本人情况核对。</p>
    <div class="row">
      <button :disabled="busy || !loaded || !availability?.matched" @click="generate">生成/更新模板草案</button>
      <button class="secondary" :disabled="busy" @click="load">刷新</button>
    </div>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="success" role="status">{{ success }}</p>
    <p v-if="availability" :role="availability.matched ? undefined : 'status'" class="muted">{{ availability.reason }} <router-link v-if="!availability.matched" to="/profile">核对基本资料</router-link></p>
    <p v-if="pending" class="muted">当前处方正在审核。生成新版会使这次待审申请失效，需要重新提交。</p>
    <div class="steps">
      <span v-for="s in flow" :key="s" :class="{ on: current?.status === s }">{{ label(s) }}</span>
    </div>
    <div v-if="current && loaded">
      <p>
        版本 <b>v{{ current.version }}</b>
        <span class="tag">{{ label(current.status) }}</span>
        <span class="tag gray">{{ current.library === "medical" ? "医疗处方" : "健身处方" }}</span>
      </p>
      <div class="row">
        <div class="stat"><span>方式</span><b style="font-size:16px">{{ current.mode }}</b></div>
        <div class="stat"><span>强度</span><b style="font-size:16px">{{ current.intensity }}</b></div>
        <div class="stat"><span>频次</span><b style="font-size:16px">{{ current.frequency }}</b></div>
        <div class="stat"><span>时长</span><b style="font-size:16px">{{ current.duration }}</b></div>
        <div class="stat"><span>周期</span><b style="font-size:16px">{{ current.cycle }}</b></div>
      </div>
      <h3>动作安排</h3>
      <ul class="ex-list">
        <li v-for="e in current.exercises || []" :key="e.id + e.name">
          <span>{{ e.name }} <span class="tag gray">{{ e.category || "训练" }}</span></span>
          <span>{{ e.sets }}组 × {{ e.reps }}{{ e.unit || "次" }}</span>
          <router-link :to="{ path: '/exercise', query: { prescription_id: current.id, exercise_id: e.id } }">练这个动作</router-link>
        </li>
      </ul>
      <h3>补充健康建议</h3>
      <p>
        饮食 <span class="tag">{{ current.health_plan?.diet || "未评估" }}</span>
        睡眠 <span class="tag">{{ current.health_plan?.sleep || "未评估" }}</span>
        用药 <span class="tag gray">{{ current.health_plan?.medication || "未评估" }}</span>
        心理 <span class="tag gray">{{ current.health_plan?.psychology || "未评估" }}</span>
      </p>
      <p class="muted">上述字段尚未接入专项评估；旧版计划中的“均衡饮食”“保证7小时”等文字来自模板，不是依据个人情况得出的建议。“未评估”不表示没有相关问题。</p>
      <p class="muted">{{ current.notes }}</p>
    </div>
    <p v-else-if="loaded" class="muted">尚无方案。{{ availability?.matched ? '可以生成模板草案查看，再交由专业人员核对。' : '基本档案和体测记录可以继续保留；暂无匹配模板时，需要项目专业人员进一步评估。' }}</p>
    <p v-else class="muted">{{ busy ? '正在加载处方…' : '处方未加载，请刷新重试。' }}</p>
  </div>
  <div class="card" v-if="current && loaded">
    <h3>提交人工审核</h3>
    <p class="muted">填写项目维护人员提供的审核账号。健身模板可交给处方师或医师；医疗模板需交给医师。审核通过后，本版标记为正式处方。</p>
    <p v-if="current.status === 'formal_prescription'" class="muted">当前版本已通过审核。生成新版后需重新送审。</p>
    <p v-else-if="pending">已提交给 {{ pending.reviewer_name }}，请等待审核。你也可以在下方记录中撤回申请。</p>
    <form v-else-if="['pre_prescription', 'monitoring'].includes(current.status)" @submit.prevent="submitReview">
      <label for="reviewer-name">审核人账号</label>
      <input id="reviewer-name" v-model="reviewerName" required minlength="2" maxlength="64" :disabled="busy" placeholder="例如 zhang-doctor" />
      <label for="request-note">补充说明（选填，最多2000字）</label>
      <textarea id="request-note" v-model="requestNote" maxlength="2000" rows="3" :disabled="busy" placeholder="写下需要审核人关注的问题"></textarea>
      <label class="review-consent"><input type="checkbox" v-model="consent" :disabled="busy" />我同意将本版处方、年龄组、身高体重、健康目标、慢病标签及最近一次测评快照提供给上述审核人。撤回或生成新版后，未处理申请将停止向审核人开放。</label>
      <button :disabled="busy || !consent || !reviewerName.trim()">提交审核</button>
    </form>
    <p v-else class="muted">当前处方状态不支持送审，请先生成新版处方。</p>
  </div>
  <div class="card">
    <h3>我的审核记录</h3>
    <p v-if="loaded && !reviews.length" class="muted">还没有送审记录。</p>
    <article class="review-item" v-for="item in reviews" :key="item.id">
      <p><b>v{{ item.prescription_snapshot.version }}</b> <span class="tag">{{ reviewStatus[item.status] }}</span> · 审核人 {{ item.reviewer_name }}（{{ roleLabel[item.reviewer_role] || item.reviewer_role }}）</p>
      <p class="muted">申请 #{{ item.id }} · {{ formatTime(item.created_at) }}</p>
      <p>提交说明：{{ item.request_note || '未填写' }}</p>
      <p v-if="item.decision_note">处理意见：{{ item.decision_note }}（{{ formatTime(item.decided_at) }}）</p>
      <details><summary>查看本次送审的内容</summary><ReviewSnapshot :prescription="item.prescription_snapshot" :profile="item.profile_snapshot" /></details>
      <button v-if="item.status === 'pending'" class="secondary" :disabled="busy" @click="cancelReview(item)">撤回申请</button>
    </article>
    <div class="row" v-if="reviewTotal > pageSize">
      <button class="secondary" :disabled="busy || offset === 0" @click="offset -= pageSize; load()">上一页</button>
      <span>第 {{ Math.floor(offset / pageSize) + 1 }} 页，共 {{ reviewTotal }} 条</span>
      <button class="secondary" :disabled="busy || offset + pageSize >= reviewTotal" @click="offset += pageSize; load()">下一页</button>
    </div>
  </div>
  <div class="card">
    <h3>处方模板库（申请书表10/11骨架）</h3>
    <div class="tpl-grid" v-if="templates">
      <div class="tpl" v-for="t in allTemplates" :key="t.id">
        <b>{{ t.name }}</b>
        <p class="muted">{{ t.mode }} · {{ t.intensity }} · {{ t.frequency }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import api, { errorMessage, getUser } from "../api/client";
import ReviewSnapshot from '../components/ReviewSnapshot.vue';
import { formatTime, reviewStatus, roleLabel } from '../utils/reviewFormat';

const LABELS = {
  clinical_intake: "临床/病史",
  fitness_assessed: "体适能评估",
  pre_prescription: "预处方",
  monitoring: "监测预效果",
  formal_prescription: "正式处方",
  implementing: "实施中",
  feedback: "监督反馈",
};
const flow = [
  "clinical_intake",
  "fitness_assessed",
  "pre_prescription",
  "monitoring",
  "formal_prescription",
  "implementing",
  "feedback",
];
const user = getUser();
const current = ref(null);
const busy = ref(false), loaded = ref(false), error = ref(''), success = ref('');
const reviews = ref([]), reviewTotal = ref(0), offset = ref(0), pending = ref(null);
const reviewerName = ref(''), requestNote = ref(''), consent = ref(false);
const pageSize = 10;
const templates = ref(null);
const availability = ref(null);
const allTemplates = computed(() => [
  ...(templates.value?.fitness?.templates || []),
  ...(templates.value?.medical?.templates || []),
]);

function label(s) {
  return LABELS[s] || s;
}

async function fetchState() {
  const [prescription, history, latestReviews, match] = await Promise.all([
    api.get(`/prescriptions/current?user_id=${user.id}`).catch(e => { if (e.response?.status === 404) return { data: null }; throw e; }),
    api.get('/prescriptions/reviews/mine', { params: { offset: offset.value, limit: pageSize } }),
    api.get('/prescriptions/reviews/mine', { params: { limit: 1 } }),
    api.get('/prescriptions/availability', { params: { user_id: user.id } }),
  ]);
  current.value = prescription.data;
  availability.value = match.data;
  reviews.value = history.data.items; reviewTotal.value = history.data.total;
  pending.value = latestReviews.data.items.find(r => r.prescription_id === current.value?.id && r.status === 'pending') || null;
  loaded.value = true;
}
async function load() {
  busy.value = true; error.value = ''; success.value = '';
  try {
    await fetchState();
  } catch (e) { loaded.value = false; error.value = errorMessage(e, '处方与审核记录加载失败，请刷新重试'); }
  finally { busy.value = false; }
}
async function mutate(action, message) {
  busy.value = true; error.value = ''; success.value = '';
  try {
    await action();
    success.value = message; offset.value = 0;
    try { await fetchState(); } catch { loaded.value = false; error.value = '操作已保存，页面刷新失败，请点击刷新。'; }
  } catch (e) { error.value = errorMessage(e); }
  finally { busy.value = false; }
}
async function generate() {
  if (busy.value || !loaded.value || !availability.value?.matched) return;
  await mutate(() => api.post('/prescriptions/generate', { user_id: user.id }), '已生成新版模板草案，请核对后送审。');
}
async function submitReview() {
  await mutate(async () => {
    await api.post(`/prescriptions/${current.value.id}/reviews`, { reviewer_username: reviewerName.value, consent: consent.value, request_note: requestNote.value });
    consent.value = false; requestNote.value = '';
  }, '已提交给指定审核人。');
}
async function cancelReview(item) {
  await mutate(() => api.post(`/prescriptions/reviews/${item.id}/cancel`), '已撤回申请。');
}
onMounted(async () => {
  await load();
  try { templates.value = (await api.get('/prescriptions/templates')).data; }
  catch { error.value = error.value || '模板库加载失败，请刷新页面重试。'; }
});
</script>

<style scoped>
form > input, form > textarea { display: block; width: 100%; margin: 8px 0 16px; }
.review-consent { display: block; margin: 12px 0; line-height: 1.7; }
.review-consent input { width: auto; }
</style>
