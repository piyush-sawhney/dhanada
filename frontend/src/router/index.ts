import { createRouter, createWebHistory } from "vue-router"
import { useAuthStore } from "../stores/auth"
import { checkBootstrapStatus } from "../api/auth"
import AuthLayout from "../components/AuthLayout.vue"
import AppLayout from "../components/AppLayout.vue"

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      redirect: "/login",
    },
    {
      path: "/bootstrap",
      name: "bootstrap",
      component: () => import("../views/BootstrapView.vue"),
      meta: { layout: AuthLayout, guest: true },
    },
    {
      path: "/login",
      name: "login",
      component: () => import("../views/LoginView.vue"),
      meta: { layout: AuthLayout, guest: true },
    },
    {
      path: "/setup",
      name: "setup",
      component: () => import("../views/SetupView.vue"),
      meta: { layout: AuthLayout },
    },
    {
      path: "/forgot-password",
      name: "forgot-password",
      component: () => import("../views/ForgotPasswordView.vue"),
      meta: { layout: AuthLayout, guest: true },
    },
    {
      path: "/reset-password",
      name: "reset-password",
      component: () => import("../views/ResetPasswordView.vue"),
      meta: { layout: AuthLayout, guest: true },
    },
    {
      path: "/dashboard",
      name: "dashboard",
      component: () => import("../views/DashboardView.vue"),
      meta: { layout: AppLayout, requiresAuth: true },
    },
  ],
})

router.beforeEach(async (to, _from) => {
  const store = useAuthStore()

  if (to.name === "bootstrap") {
    return true
  }

  if (to.name === "setup") {
    if (store.isSetupRequired) {
      return true
    }
    if (store.isAuthenticated) {
      return { name: "dashboard" }
    }
    return { name: "login" }
  }

  if (to.name === "login" || to.name === "forgot-password" || to.name === "reset-password") {
    if (store.isAuthenticated) {
      return { name: "dashboard" }
    }

    if (to.name === "login") {
      try {
        const { needs_bootstrap } = await checkBootstrapStatus()
        if (needs_bootstrap) {
          return { name: "bootstrap" }
        }
      } catch {
      }
    }

    return true
  }

  if (to.meta.requiresAuth) {
    if (!store.isAuthenticated) {
      return { name: "login" }
    }
    if (!store.user) {
      await store.checkAuth()
    }
    return true
  }

  return true
})

export default router
