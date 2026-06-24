<script setup lang="ts">
import { shallowRef } from "vue"
import { useRouter } from "vue-router"
import { useAdminStore } from "../../stores/admin"
import { createRole } from "../../api/admin"
import AdminNav from "../../components/AdminNav.vue"

const router = useRouter()
const admin = useAdminStore()

const name = shallowRef("")
const description = shallowRef("")
const error = shallowRef("")
const loading = shallowRef(false)

async function handleSubmit() {
  error.value = ""
  loading.value = true

  try {
    await createRole(name.value, description.value || undefined)
    admin.fetchRoles()
    router.push({ name: "admin-roles" })
  } catch (err: any) {
    error.value = err.response?.data?.detail ?? "Failed to create role"
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div>
    <AdminNav />
    <form @submit.prevent="handleSubmit" class="max-w-lg space-y-5">
      <h2 class="text-xl font-semibold text-gray-900">New Role</h2>

      <div v-if="error" class="rounded-lg bg-red-50 p-3 text-sm text-red-700">{{ error }}</div>

      <div>
        <label class="block text-sm font-medium text-gray-700">Name *</label>
        <input v-model="name" type="text" required
          class="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-200 focus:outline-none" />
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700">Description</label>
        <textarea v-model="description" rows="3"
          class="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-200 focus:outline-none" />
      </div>

      <button type="submit" :disabled="loading"
        class="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50">
        {{ loading ? "Creating..." : "Create Role" }}
      </button>
    </form>
  </div>
</template>
