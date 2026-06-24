<script setup lang="ts">
import { onMounted, shallowRef } from "vue"
import { useRouter } from "vue-router"
import { useAdminStore } from "../../stores/admin"
import { createUser, registerUserApp } from "../../api/admin"
import AdminNav from "../../components/AdminNav.vue"

const router = useRouter()
const admin = useAdminStore()

const email = shallowRef("")
const username = shallowRef("")
const fullName = shallowRef("")
const roleName = shallowRef("")
const selectedApps = shallowRef<string[]>([])
const error = shallowRef("")
const loading = shallowRef(false)
const created = shallowRef<{ id: string; email: string } | null>(null)

onMounted(() => {
  if (admin.roles.length === 0) admin.fetchRoles()
  if (admin.allApps.length === 0) admin.fetchAllApps()
})

function toggleApp(slug: string) {
  const idx = selectedApps.value.indexOf(slug)
  if (idx >= 0) selectedApps.value.splice(idx, 1)
  else selectedApps.value.push(slug)
}

async function handleSubmit() {
  error.value = ""
  loading.value = true

  try {
    const user = await createUser({
      email: email.value,
      username: username.value || undefined,
      full_name: fullName.value || undefined,
      role_name: roleName.value || undefined,
    })

    for (const slug of selectedApps.value) {
      await registerUserApp(user.id, slug)
    }

    created.value = { id: user.id, email: user.email }
  } catch (err: any) {
    error.value = err.response?.data?.detail ?? "Failed to create user"
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div>
    <AdminNav />

    <div v-if="created" class="space-y-5">
      <h2 class="text-xl font-semibold text-gray-900">User Created</h2>
      <div class="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-800">
        <p>Verification email and temporary password sent to <strong>{{ created.email }}</strong>.</p>
      </div>
      <button
        class="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
        @click="router.push({ name: 'admin-users' })"
      >
        Back to Users
      </button>
      <button
        class="ml-2 rounded-lg border px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50"
        @click="created = null; email = ''; username = ''; fullName = ''; roleName = ''; selectedApps = []"
      >
        Create Another
      </button>
    </div>

    <form v-else @submit.prevent="handleSubmit" class="max-w-lg space-y-5">
      <h2 class="text-xl font-semibold text-gray-900">New User</h2>

      <div v-if="error" class="rounded-lg bg-red-50 p-3 text-sm text-red-700">{{ error }}</div>

      <div>
        <label class="block text-sm font-medium text-gray-700">Email *</label>
        <input v-model="email" type="email" required
          class="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-200 focus:outline-none" />
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700">Username</label>
        <input v-model="username" type="text"
          class="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-200 focus:outline-none" />
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700">Full Name</label>
        <input v-model="fullName" type="text"
          class="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-200 focus:outline-none" />
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700">Role</label>
        <select v-model="roleName"
          class="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-200 focus:outline-none">
          <option value="">None</option>
          <option v-for="role in admin.roles" :key="role.name" :value="role.name">{{ role.name }}</option>
        </select>
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700">App Access</label>
        <div class="mt-1 space-y-1">
          <label v-for="app in admin.allApps" :key="app.slug" class="flex items-center gap-2 text-sm">
            <input type="checkbox" :checked="selectedApps.includes(app.slug)" @change="toggleApp(app.slug)"
              class="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
            {{ app.name }}
          </label>
        </div>
      </div>

      <button type="submit" :disabled="loading"
        class="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50">
        {{ loading ? "Creating..." : "Create User" }}
      </button>
    </form>
  </div>
</template>
