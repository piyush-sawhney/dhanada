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
      path: "/recovery/email-sent",
      name: "recovery-email-sent",
      component: () => import("../views/RecoveryEmailSentView.vue"),
      meta: { layout: AuthLayout, guest: true },
    },
    {
      path: "/recovery/approve",
      name: "recovery-approve",
      component: () => import("../views/RecoveryApprovalView.vue"),
      meta: { layout: AuthLayout, guest: true },
    },
    {
      path: "/verify-email",
      name: "verify-email",
      component: () => import("../views/VerifyEmailView.vue"),
      meta: { layout: AuthLayout },
    },
    {
      path: "/dashboard",
      name: "dashboard",
      component: () => import("../views/DashboardView.vue"),
      meta: { layout: AppLayout, requiresAuth: true },
    },
    {
      path: "/crm",
      redirect: "/crm/clients",
    },
    {
      path: "/crm/clients",
      name: "crm-clients",
      component: () => import("../views/crm/ClientsView.vue"),
      meta: { layout: AppLayout, requiresAuth: true },
    },
    {
      path: "/admin",
      redirect: "/admin/users",
      meta: { layout: AppLayout, requiresAuth: true, requiresSuperuser: true },
    },
    {
      path: "/admin/users",
      name: "admin-users",
      component: () => import("../views/admin/UsersListView.vue"),
      meta: { layout: AppLayout, requiresAuth: true, requiresSuperuser: true },
    },
    {
      path: "/admin/users/new",
      name: "admin-users-new",
      component: () => import("../views/admin/UserCreateView.vue"),
      meta: { layout: AppLayout, requiresAuth: true, requiresSuperuser: true },
    },
    {
      path: "/admin/users/:id",
      name: "admin-users-id",
      component: () => import("../views/admin/UserDetailView.vue"),
      meta: { layout: AppLayout, requiresAuth: true, requiresSuperuser: true },
    },
    {
      path: "/admin/roles",
      name: "admin-roles",
      component: () => import("../views/admin/RolesListView.vue"),
      meta: { layout: AppLayout, requiresAuth: true, requiresSuperuser: true },
    },
    {
      path: "/admin/roles/new",
      name: "admin-roles-new",
      component: () => import("../views/admin/RoleCreateView.vue"),
      meta: { layout: AppLayout, requiresAuth: true, requiresSuperuser: true },
    },
    {
      path: "/admin/roles/:name",
      name: "admin-roles-name",
      component: () => import("../views/admin/RoleDetailView.vue"),
      meta: { layout: AppLayout, requiresAuth: true, requiresSuperuser: true },
    },
  ],
})

router.beforeEach(async (to, _from) => {
  const store = useAuthStore()

  if (to.name === "bootstrap") {
    return true
  }

  // Global bootstrap check — redirect any route to /bootstrap if no users exist
  if (!store.isAuthenticated && !store.bootstrapChecked) {
    try {
      const { needs_bootstrap } = await checkBootstrapStatus()
      if (needs_bootstrap) {
        return { name: "bootstrap" }
      }
    } catch {
    }
    store.bootstrapChecked = true
  }

  // Guest routes (login, forgot-password, reset-password, recovery)
  if (to.name === "login" || to.name === "forgot-password" || to.name === "reset-password" || to.name === "recovery-email-sent" || to.name === "recovery-approve") {
    if (store.isAuthenticated) {
      return { name: "dashboard" }
    }
    return true
  }

  // Setup route
  if (to.name === "setup") {
    if (store.isSetupRequired) {
      return true
    }
    if (store.isAuthenticated) {
      return { name: "dashboard" }
    }
    return { name: "login" }
  }

  // Protected routes
  if (to.meta.requiresAuth) {
    if (!store.isAuthenticated) {
      return { name: "login" }
    }
    await store.checkAuth()
    if (!store.isAuthenticated) {
      return { name: "login" }
    }
    if (to.meta.requiresSuperuser && !store.user?.is_superuser) {
      return { name: "dashboard" }
    }
    return true
  }

  return true
})

export default router
