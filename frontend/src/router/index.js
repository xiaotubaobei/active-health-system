import { createRouter, createWebHistory } from "vue-router";
import api, { clearUser, getUser, setUser } from "../api/client";

const routes = [
  { path: "/login", name: "login", component: () => import("../views/Login.vue") },
  { path: "/onboarding", name: "onboarding", component: () => import("../views/Onboarding.vue") },
  { path: "/history", name: "history", component: () => import("../views/History.vue") },
  { path: "/", name: "home", component: () => import("../views/Home.vue") },
  { path: "/profile", name: "profile", component: () => import("../views/Profile.vue") },
  { path: "/fitness", name: "fitness", component: () => import("../views/Fitness.vue") },
  { path: "/body", name: "body", component: () => import("../views/BodyParse.vue") },
  { path: "/prescription", name: "prescription", component: () => import("../views/Prescription.vue") },
  { path: "/exercise", name: "exercise", component: () => import("../views/Exercise.vue") },
  { path: "/report", name: "report", component: () => import("../views/Report.vue") },
  { path: "/admin", name: "admin", component: () => import("../views/Admin.vue") },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to) => {
  if (to.path === "/login") return true;
  const user = getUser();
  if (!user) return "/login";
  if (to.path === "/onboarding") return true;
  try {
    const { data } = await api.get("/onboarding/status", { params: { user_id: user.id }, timeout: 5000 });
    setUser({ ...user, onboarding_done: data.onboarding_done, privacy_consent: data.privacy_consent });
    if (!data.onboarding_done) return "/onboarding";
  } catch (error) {
    if (error?.response?.status === 404) {
      clearUser();
      return "/login";
    }
    return "/onboarding";
  }
  return true;
});

export default router;
