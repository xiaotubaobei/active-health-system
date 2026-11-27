<template>
  <section class="card" aria-labelledby="account-security-heading">
    <h2 id="account-security-heading">账号安全</h2>
    <p class="muted">当前账号：{{ user?.username }}</p>
    <p v-if="user?.username === 'demo'" class="muted">演示账号不支持修改密码，请退出后注册自己的账号。</p>
    <template v-else>
      <p id="password-help" class="muted">新密码需要 8–128 个字符。修改成功后，当前设备和其他设备都需要重新登录，训练记录会保留。</p>
      <form @submit.prevent="submit" aria-describedby="password-help">
        <input class="username" :value="user?.username" autocomplete="username" readonly tabindex="-1" aria-label="用户名" />
        <fieldset :disabled="busy || uncertain || changed">
          <legend>修改密码</legend>
          <label>当前密码 <input v-model="current" type="password" autocomplete="current-password" maxlength="128" required /></label>
          <label>新密码 <input v-model="next" type="password" autocomplete="new-password" minlength="8" maxlength="128" required /></label>
          <label>再输一次新密码 <input v-model="confirmation" type="password" autocomplete="new-password" minlength="8" maxlength="128" required /></label>
          <button type="submit">{{ busy ? '正在修改…' : '修改密码并重新登录' }}</button>
        </fieldset>
      </form>
      <p v-if="busy" class="muted" role="status">正在处理，请稍等片刻。</p>
      <p v-if="changed" class="ok" role="status">密码已修改，请用新密码重新登录。</p>
      <p v-if="error" class="err" role="alert">{{ error }}</p>
      <button v-if="uncertain || changed" type="button" class="secondary" @click="signIn">前往登录</button>
    </template>
  </section>
</template>

<script setup>
import { onBeforeUnmount, onMounted } from "vue";
import { onBeforeRouteLeave, useRouter } from "vue-router";
import api, { clearUser, errorMessage, getUser } from "../api/client";
import { usePasswordChange } from "../composables/usePasswordChange";

const user = getUser(), router = useRouter();
async function signIn() { clearUser(); await router.replace({ path: "/login" }); }
const state = usePasswordChange({ api, errorMessage, onSignIn: signIn,
  onChanged: async () => { clearUser(); await router.replace({ path: "/login", query: { password_changed: "1" } }); } });
const { current, next, confirmation, busy, error, uncertain, changed, submit } = state;
function beforeUnload(event) {
  if (busy.value && !changed.value) { event.preventDefault(); event.returnValue = ""; }
}
onBeforeRouteLeave(to => !busy.value || changed.value || to.path === "/login");
onMounted(() => window.addEventListener("beforeunload", beforeUnload));
onBeforeUnmount(() => { state.dispose(); window.removeEventListener("beforeunload", beforeUnload); });
</script>

<style scoped>
form { position: relative; }
fieldset { display: grid; gap: 14px; border: 0; padding: 0; margin: 16px 0 0; min-width: 0; max-width: 440px; }
legend { font-weight: 600; margin-bottom: 12px; }
label { display: grid; gap: 6px; }
input, button { min-height: 44px; max-width: 100%; box-sizing: border-box; }
.username { position: absolute; left: 0; top: 0; width: 1px; height: 1px; min-height: 0; padding: 0; border: 0; clip-path: inset(50%); }
</style>
