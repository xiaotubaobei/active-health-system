import { createRouter, createWebHistory } from "vue-router";
import { getUser } from "../api/client";

const routes = [
  { path: "/login", name: "login", component: () => import("../views/Login.vue") },
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

router.beforeEach((to) => {
  if (to.path !== "/login" && !getUser()) return "/login";
  return true;
});

export default router;
