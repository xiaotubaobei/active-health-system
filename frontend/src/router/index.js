import { createRouter, createWebHistory } from "vue-router";
import api, { clearUser, setUser } from "../api/client";

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
  try {
    const { data: user } = await api.get("/users/me", { timeout: 5000 });
    setUser(user);
    if (to.path !== "/onboarding" && !user.onboarding_done) return "/onboarding";
  } catch (error) {
    if ([401, 404].includes(error?.response?.status)) {
      clearUser();
      return "/login";
    }
    return { path: "/login", query: { unavailable: "1" } };
  }
  return true;
});

export default router;
