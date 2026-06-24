<script setup lang="ts">
import { onMounted, shallowRef } from "vue"
import { useRoute, useRouter } from "vue-router"
import { useAdminStore } from "../../stores/admin"
import { useAuthStore } from "../../stores/auth"
import {
  getUser, updateUser, deleteUser, resetUserAuth, resendWelcome,
  getUserRoles, assignRole, revokeRole,
  getUserApps, registerUserApp, unregisterUserApp,
} from "../../api/admin"
import type { UserAdminResponse } from "../../types/admin"
import AdminNav from "../../components/AdminNav.vue"

const route = useRoute()
const router = useRouter()
const admin = useAdminStore()
const authStore = useAuthStore()

const isSelf = () => authStore.user?.id === userId

const userId = route.params.id as string

const user = shallowRef<UserAdminResponse | null>(null)
const roles = shallowRef<string[]>([])
const apps = shallowRef<string[]>([])
const tab = shallowRef<"info" | "roles" | "apps">("info")
const error = shallowRef("")
const loading = shallowRef(false)
const resetMessage = shallowRef<string | null>(null)

onMounted(async () => {
  loading.value = true
  try {
    user.value = await getUser(userId)
    roles.value = await getUserRoles(userId)
    apps.value = await getUserApps(userId)
    if (admin.roles.length === 0) admin.fetchRoles()
    if (admin.allApps.length === 0) admin.fetchAllApps()
  } catch {
    error.value = "Failed to load user"
  } finally {
    loading.value = false
  }
})

async function toggleActive() {
  if (!user.value) return
  const updated = await updateUser(userId, { is_active: !user.value.is_active })
  user.value = updated
}

async function handleDelete() {
  if (!confirm(`Delete user "${user.value?.email}"?`)) return
  await deleteUser(userId)
  router.push({ name: "admin-users" })
}

async function handleResetAuth() {
  if (!confirm("Reset authentication for this user? This will disable TOTP and set a new temporary password.")) return
  const result = await resetUserAuth(userId)
  resetMessage.value = result.message
}

async function handleResendWelcome() {
  if (!confirm("Resend welcome email with a new temporary password and verification link?")) return
  const result = await resendWelcome(userId)
  resetMessage.value = result.message
}

async function handleAssignRole(roleName: string) {
  await assignRole(userId, roleName)
  roles.value = await getUserRoles(userId)
}

async function handleRevokeRole(roleName: string) {
  await revokeRole(userId, roleName)
  roles.value = await getUserRoles(userId)
}

async function handleRegisterApp(slug: string) {
  await registerUserApp(userId, slug)
  apps.value = await getUserApps(userId)
}

async function handleUnregisterApp(slug: string) {
  await unregisterUserApp(userId, slug)
  apps.value = await getUserApps(userId)
}

const selectedRole = shallowRef("")
const selectedApp = shallowRef("")

const availableRoles = () => admin.roles.filter(r => !roles.value.includes(r.name))
const availableApps = () => admin.allApps.filter(a => !apps.value.includes(a.slug))
</script>

<template>
  <div>
    <AdminNav />

    <div v-if="loading" class="py-8 text-center text-sm text-gray-400">Loading...</div>

    <template v-else-if="user">
      <div class="mb-4 flex items-center gap-3">
        <router-link :to="{ name: 'admin-users' }" class="text-sm text-blue-600 hover:underline">← Users</router-link>
        <h2 class="text-xl font-semibold text-gray-900">{{ user.email }}</h2>
      </div>

      <div v-if="error" class="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{{ error }}</div>

      <div v-if="resetMessage" class="mb-4 rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-800">
        <p>{{ resetMessage }}</p>
      </div>

      <div class="mb-4 flex gap-4 border-b">
        <button v-for="t in ['info', 'roles', 'apps'] as const" :key="t"
          class="px-4 py-2 text-sm font-medium transition"
          :class="tab === t ? 'border-b-2 border-blue-600 text-blue-700' : 'text-gray-500 hover:text-gray-700'"
          @click="tab = t">
          {{ t.charAt(0).toUpperCase() + t.slice(1) }}
        </button>
      </div>

      <!-- Info Tab -->
      <div v-if="tab === 'info'" class="max-w-lg space-y-4">
        <div class="rounded-lg border p-4">
          <dl class="space-y-2 text-sm">
            <div class="flex justify-between">
              <dt class="text-gray-500">Email</dt>
              <dd>{{ user.email }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-gray-500">Username</dt>
              <dd>{{ user.username || "—" }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-gray-500">Full Name</dt>
              <dd>{{ user.full_name || "—" }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-gray-500">Active</dt>
              <dd>
                <span class="inline-block h-2 w-2 rounded-full" :class="user.is_active ? 'bg-green-500' : 'bg-red-400'" />
                {{ user.is_active ? "Active" : "Inactive" }}
              </dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-gray-500">Superuser</dt>
              <dd>{{ user.is_superuser ? "Yes" : "No" }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-gray-500">Verified</dt>
              <dd>{{ user.email_verified ? "Yes" : "No" }}</dd>
            </div>
          </dl>
        </div>

        <div class="flex flex-wrap gap-3">
          <button v-if="!user.is_superuser"
            class="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
            @click="toggleActive">
            {{ user.is_active ? "Deactivate" : "Activate" }}
          </button>
          <button v-if="!user.is_superuser"
            class="rounded-lg border border-red-300 px-4 py-2 text-sm font-semibold text-red-700 hover:bg-red-50"
            @click="handleResetAuth">
            Reset Auth
          </button>
          <button v-if="!user.is_superuser"
            class="rounded-lg border border-amber-300 px-4 py-2 text-sm font-semibold text-amber-700 hover:bg-amber-50"
            @click="handleResendWelcome">
            Resend Welcome
          </button>
          <button v-if="!user.is_superuser && !isSelf()"
            class="rounded-lg border border-red-300 px-4 py-2 text-sm font-semibold text-red-700 hover:bg-red-50"
            @click="handleDelete">
            Delete
          </button>
        </div>
      </div>

      <!-- Roles Tab -->
      <div v-if="tab === 'roles'" class="max-w-lg space-y-4">
        <div class="flex flex-wrap gap-2">
          <span v-for="r in roles" :key="r"
            class="flex items-center gap-1 rounded bg-blue-100 px-3 py-1 text-sm text-blue-700">
            {{ r }}
            <button class="text-blue-500 hover:text-red-600" @click="handleRevokeRole(r)">×</button>
          </span>
          <span v-if="roles.length === 0" class="text-sm text-gray-400">No roles assigned.</span>
        </div>

        <div v-if="availableRoles().length > 0" class="flex gap-2">
          <select v-model="selectedRole" class="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none">
            <option v-for="r in availableRoles()" :key="r.name" :value="r.name">{{ r.name }}</option>
          </select>
          <button class="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
            @click="handleAssignRole(selectedRole)">
            Add Role
          </button>
        </div>
        <p v-else class="text-xs text-gray-400">User has all available roles.</p>
      </div>

      <!-- Apps Tab -->
      <div v-if="tab === 'apps'" class="max-w-lg space-y-4">
        <div class="flex flex-wrap gap-2">
          <span v-for="s in apps" :key="s"
            class="flex items-center gap-1 rounded bg-green-100 px-3 py-1 text-sm text-green-700">
            {{ s }}
            <button class="text-green-500 hover:text-red-600" @click="handleUnregisterApp(s)">×</button>
          </span>
          <span v-if="apps.length === 0" class="text-sm text-gray-400">No app access.</span>
        </div>

        <div v-if="availableApps().length > 0" class="flex gap-2">
          <select v-model="selectedApp" class="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none">
            <option v-for="a in availableApps()" :key="a.slug" :value="a.slug">{{ a.name }}</option>
          </select>
          <button class="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
            @click="handleRegisterApp(selectedApp)">
            Register App
          </button>
        </div>
        <p v-else class="text-xs text-gray-400">User is registered to all apps.</p>
      </div>
    </template>

    <div v-else-if="error" class="py-8 text-center text-sm text-red-600">{{ error }}</div>
  </div>
</template>
