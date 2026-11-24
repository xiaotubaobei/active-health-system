import { createRouter, createWebHistory } from "vue-router";
import api, { clearUser, getUser, setUser } from "../api/client";
import { createAuthGuard } from "../utils/authNavigation";

const routes = [
  { path: "/login", name: "login", component: () => import("../views/Login.vue") },
  { path: "/connection", name: "connection", component: () => import("../views/Connection.vue") },
  { path: "/onboarding", name: "onboarding", component: () => import("../views/Onboarding.vue") },
  { path: "/history", name: "history", component: () => import("../views/History.vue") },
  { path: "/", name: "home", component: () => import("../views/Home.vue") },
  { path: "/profile", name: "profile", component: () => import("../views/Profile.vue") },
  { path: "/fitness", name: "fitness", component: () => import("../views/Fitness.vue") },
  { path: "/body", name: "body", component: () => import("../views/BodyParse.vue") },
  { path: "/prescription", name: "prescription", component: () => import("../views/Prescription.vue") },
  { path: "/reviews", name: "reviews", component: () => import("../views/Reviews.vue") },
  { path: "/exercise", name: "exercise", component: () => import("../views/Exercise.vue") },
  { path: "/report", name: "report", component: () => import("../views/Report.vue") },
  { path: "/admin", name: "admin", component: () => import("../views/Admin.vue") },
  { path: "/:pathMatch(.*)*", name: "not-found", component: () => import("../views/NotFound.vue") },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(createAuthGuard({ api, getUser, setUser, clearUser }));

export default router;
