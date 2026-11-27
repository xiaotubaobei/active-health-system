import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";
import "./assets/style.css";

createApp(App).use(router).mount("#app");

if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register(`${import.meta.env.BASE_URL}sw.js`, {
        scope: import.meta.env.BASE_URL,
        updateViaCache: "none",
      })
      .then((registration) => registration.update())
      .catch((error) => {
        console.warn("Service Worker 注册失败，页面将继续使用在线模式。", error);
      });
  });
}
