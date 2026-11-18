<template>
  <div class="card">
    <h2>处方人工审核</h2>
    <p class="muted">仅显示用户指定给你的申请。查看送审时的处方与资料，再填写审核意见。</p>
    <p v-if="!canReview">当前账号没有审核权限。请由项目维护人员为个人账号开通处方师或医师角色。</p>
    <template v-else>
      <div class="row">
        <label>查看范围 <select v-model="status" :disabled="busy" @change="offset = 0; load()">
          <option value="pending">待审核</option><option value="approved">已通过</option><option value="rejected">已退回</option>
        </select></label>
        <button class="secondary" :disabled="busy" @click="load">刷新</button>
      </div>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="success" role="status">{{ success }}</p>
      <p v-if="!loaded && busy" class="muted">正在加载申请…</p>
      <p v-else-if="loaded && !items.length" class="muted">当前没有{{ reviewStatus[status] }}的申请。</p>
      <article class="review-item" v-for="item in items" :key="item.id">
        <h3>{{ item.requester_name }} · v{{ item.prescription_snapshot.version }} <span class="tag">{{ reviewStatus[item.status] }}</span></h3>
        <p class="muted">申请编号 #{{ item.id }} · 提交时间 {{ formatTime(item.created_at) }}</p>
        <p>用户说明：{{ item.request_note || '未填写' }}</p>
        <details><summary>查看处方、档案和测评快照</summary><ReviewSnapshot :prescription="item.prescription_snapshot" :profile="item.profile_snapshot" /></details>
        <template v-if="item.status === 'pending'">
          <label :for="`note-${item.id}`">审核意见（必填，最多2000字）</label>
          <textarea :id="`note-${item.id}`" v-model="notes[item.id]" maxlength="2000" rows="3" :disabled="busy" placeholder="说明通过的依据，或需要补充、修改的内容"></textarea>
          <p class="muted">通过后，这一版会标记为正式处方；退回保留原处方，用户可按意见调整后重新送审。</p>
          <div class="row">
            <button :disabled="busy || !notes[item.id]?.trim()" @click="decide(item, 'approved')">审核通过</button>
            <button class="secondary" :disabled="busy || !notes[item.id]?.trim()" @click="decide(item, 'rejected')">退回补充</button>
          </div>
        </template>
        <template v-else><p>审核意见：{{ item.decision_note }}</p><p class="muted">处理时间 {{ formatTime(item.decided_at) }}</p></template>
      </article>
      <div class="row" v-if="total > pageSize">
        <button class="secondary" :disabled="busy || offset === 0" @click="offset -= pageSize; load()">上一页</button>
        <span>第 {{ Math.floor(offset / pageSize) + 1 }} 页，共 {{ total }} 条</span>
        <button class="secondary" :disabled="busy || offset + pageSize >= total" @click="offset += pageSize; load()">下一页</button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import api, { errorMessage, getUser } from '../api/client';
import ReviewSnapshot from '../components/ReviewSnapshot.vue';
import { formatTime, reviewStatus } from '../utils/reviewFormat';
const canReview = ['physician', 'prescription_specialist'].includes(getUser()?.role);
const items = ref([]), total = ref(0), offset = ref(0), status = ref('pending'), notes = ref({});
const busy = ref(false), error = ref(''), success = ref(''), loaded = ref(false);
const pageSize = 10;
async function fetchItems() {
  const { data } = await api.get('/prescriptions/reviews/inbox', { params: { status: status.value, offset: offset.value, limit: pageSize } });
  items.value = data.items; total.value = data.total; loaded.value = true;
}
async function load() {
  busy.value = true; error.value = ''; success.value = '';
  try { await fetchItems(); } catch (e) { items.value = []; loaded.value = false; error.value = errorMessage(e, '审核列表加载失败，请刷新重试'); }
  finally { busy.value = false; }
}
async function decide(item, decision) {
  busy.value = true; error.value = ''; success.value = '';
  try {
    await api.post(`/prescriptions/reviews/${item.id}/decision`, { decision, note: notes.value[item.id] });
    delete notes.value[item.id];
    success.value = decision === 'approved' ? '已通过，用户可以回看审核结果。' : '已退回，用户可以查看你的意见。';
    if (items.value.length === 1 && offset.value > 0) offset.value -= pageSize;
    try { await fetchItems(); } catch { items.value = []; loaded.value = false; error.value = '结果已保存，列表刷新失败，请点击刷新。'; }
  } catch (e) { error.value = errorMessage(e, '审核未保存，请重试'); }
  finally { busy.value = false; }
}
onMounted(() => { if (canReview) load(); });
</script>
