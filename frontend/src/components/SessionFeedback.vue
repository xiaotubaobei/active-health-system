<template>
  <section class="feedback" aria-labelledby="feedback-heading">
    <h3 id="feedback-heading">这次练得怎么样？</h3>
    <p class="muted">可以选填，之后也能从训练历史打开报告补填或修改。这里记录的是你自己的感受；不会替代动作评分，也不会自动修改训练计划。</p>
    <p v-if="loading" role="status">正在读取反馈…</p>
    <div v-else-if="loadError">
      <p class="err" role="alert">{{ loadError }}</p>
      <button class="secondary" @click="load">重新加载反馈</button>
    </div>
    <form v-else-if="loaded" @submit.prevent="save">
      <fieldset :disabled="saving || conflict">
        <legend>本次训练反馈</legend>
        <label>这次是否实际训练？
          <select v-model="form.performed" required @change="participationChanged">
            <option value="" disabled>请选择</option>
            <option value="training">本人实际做了训练</option>
            <option value="demo">仅体验演示或查看样本</option>
          </select>
        </label>
        <template v-if="form.performed === 'training'">
          <label>完成情况
            <select v-model="form.completion" required>
              <option value="" disabled>请选择</option>
              <option value="completed">完成了本次安排</option>
              <option value="partial">只完成了一部分</option>
              <option value="stopped">提前停止了</option>
            </select>
          </label>
          <label>你觉得累不累？
            <select v-model="form.effort" required>
              <option value="" disabled>请选择</option>
              <option value="easy">比较轻松</option>
              <option value="moderate">强度合适</option>
              <option value="hard">比较吃力</option>
            </select>
          </label>
          <label>这次有没有不适？
            <select v-model="form.discomfort" required>
              <option value="" disabled>请选择</option>
              <option value="no">没有</option>
              <option value="yes">有，可以在下方说明</option>
            </select>
          </label>
        </template>
        <p v-if="form.performed === 'demo'" class="muted">会标记为体验记录，不记录本人的完成情况、费力程度或不适情况。</p>
        <label>补充说明（选填）
          <textarea v-model="form.note" maxlength="1000" rows="3" aria-describedby="feedback-note-count" placeholder="例如：最后一组没做完，下次想再试试。"></textarea>
        </label>
        <span id="feedback-note-count" class="muted count">{{ form.note.length }} / 1000</span>
        <button type="submit" :disabled="!dirty">{{ saving ? '正在保存…' : revision ? '保存修改' : '保存反馈' }}</button>
      </fieldset>
      <p v-if="dirty" class="muted" role="status">有反馈尚未保存，离开前请先保存。</p>
      <p v-else-if="savedAt" class="ok" role="status">反馈已保存 · {{ savedTime }}</p>
      <p v-if="saveError" class="err" role="alert">{{ saveError }}</p>
      <button v-if="conflict" type="button" class="secondary" @click="reload">重新加载已保存的反馈</button>
    </form>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, watch } from "vue";
import { onBeforeRouteLeave, onBeforeRouteUpdate } from "vue-router";
import api, { errorMessage } from "../api/client";
import { useSessionFeedback } from "../composables/useSessionFeedback";

const props = defineProps({ sessionId: { type: Number, required: true } });
const state = useSessionFeedback({ api, sessionId: () => props.sessionId, errorMessage });
const { form, loaded, loading, saving, loadError, saveError, conflict, revision, savedAt, dirty,
  participationChanged, load, save } = state;
const savedTime = computed(() => savedAt.value ? new Date(`${savedAt.value}Z`).toLocaleString("zh-CN") : "");

function confirmLeave() {
  return !(dirty.value || saving.value) || window.confirm("还有反馈未确认保存，离开会丢失本页填写的内容。确定离开吗？");
}
function reload() { if (confirmLeave()) load(); }
function beforeUnload(event) {
  if (dirty.value || saving.value) { event.preventDefault(); event.returnValue = ""; }
}
defineExpose({ confirmLeave });
watch(() => props.sessionId, load, { immediate: true });
onBeforeRouteLeave(confirmLeave);
onBeforeRouteUpdate((to, from) => to.query.session_id === from.query.session_id || confirmLeave());
onMounted(() => window.addEventListener("beforeunload", beforeUnload));
onBeforeUnmount(() => { state.dispose(); window.removeEventListener("beforeunload", beforeUnload); });
</script>

<style scoped>
.feedback { margin: 20px 0; padding-top: 4px; border-top: 1px solid var(--line); }
fieldset { border: 0; padding: 0; margin: 0; min-width: 0; display: grid; gap: 14px; }
legend { padding: 0; margin-bottom: 12px; font-weight: 600; }
label { display: grid; gap: 8px; }
select, textarea { width: 100%; min-width: 0; min-height: 44px; }
textarea { resize: vertical; }
button { min-height: 44px; justify-self: start; }
.count { margin-top: -8px; text-align: right; font-size: 12px; }
</style>
