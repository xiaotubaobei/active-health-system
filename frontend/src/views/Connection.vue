<template>
  <div class="card" role="alert">
    <h2>暂时连接不上系统</h2>
    <p>请检查网络后重试。恢复连接后，会继续打开刚才的页面。</p>
    <p class="muted">这不代表账号已退出。已经保存的记录会保留；尚未提交的内容请在原页面核对。</p>
    <button :disabled="busy" @click="retry">{{ busy ? '正在重新连接…' : '重新连接' }}</button>
    <router-link to="/login" style="margin-left:16px">返回登录</router-link>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { safeReturnPath } from "../utils/authNavigation";
const route = useRoute();
const router = useRouter();
const busy = ref(false);
async function retry() {
  busy.value = true;
  try { await router.replace(safeReturnPath(route.query.next)); }
  finally { busy.value = false; }
}
</script>
