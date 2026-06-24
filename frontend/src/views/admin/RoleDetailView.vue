<script setup lang="ts">
import { onMounted, shallowRef } from "vue"
import { useRoute, useRouter } from "vue-router"
import { getRole, addPermission, removePermission, listUsers } from "../../api/admin"
import type { RoleResponse, UserAdminResponse } from "../../types/admin"
import AdminNav from "../../components/AdminNav.vue"

const route = useRoute()
const router = useRouter()

const role = shallowRef<RoleResponse | null>(null)
const users = shallowRef<UserAdminResponse[]>([])
const newResource = shallowRef("")
const newAction = shallowRef("")
const newPermissionError = shallowRef("")
const error = shallowRef("")
const loading = shallowRef(false)

onMounted(async () => {
  loading.value = true
  try {
    role.value = await getRole(route.params.name as string)
    const res = await listUsers()
    users.value = res.users.filter(u => u.roles.includes(route.params.name as string))
  } catch {
    error.value = "Failed to load role"
  } finally {
    loading.value = false
  }
})

async function handleAddPermission() {
  if (!newResource.value || !newAction.value || !role.value) return
  newPermissionError.value = ""

  try {
    await addPermission(role.value.name, newResource.value, newAction.value)
    role.value = await getRole(role.value.name)
    newResource.value = ""
    newAction.value = ""
  } catch (err: any) {
    newPermissionError.value = err.response?.data?.detail ?? "Failed to add permission"
  }
}

async function handleRemovePermission(resource: string, action: string) {
  if (!role.value) return
  await removePermission(role.value.name, resource, action)
  role.value = await getRole(role.value.name)
}
</script>

<template>
  <div>
    <AdminNav />

    <div v-if="loading" class="py-8 text-center text-sm text-gray-400">Loading...</div>

    <template v-else-if="role">
      <div class="mb-4 flex items-center gap-3">
        <router-link :to="{ name: 'admin-roles' }" class="text-sm text-blue-600 hover:underline">← Roles</router-link>
        <h2 class="text-xl font-semibold text-gray-900">{{ role.name }}</h2>
        <span v-if="role.is_system" class="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-700">System</span>
      </div>

      <div v-if="error" class="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{{ error }}</div>

      <div v-if="role.description" class="mb-4 text-sm text-gray-500">{{ role.description }}</div>

      <!-- Permissions -->
      <div class="mb-6">
        <h3 class="mb-2 text-sm font-semibold text-gray-700">Permissions</h3>
        <div class="overflow-x-auto rounded-lg border">
          <table class="min-w-full divide-y divide-gray-200 text-sm">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-2 text-left font-medium text-gray-600">Resource</th>
                <th class="px-4 py-2 text-left font-medium text-gray-600">Action</th>
                <th class="px-4 py-2 text-right font-medium text-gray-600"></th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr v-for="(perm, i) in role.permissions" :key="i">
                <td class="px-4 py-2 font-mono text-xs">{{ perm.resource }}</td>
                <td class="px-4 py-2 font-mono text-xs">{{ perm.action }}</td>
                <td class="px-4 py-2 text-right">
                  <button class="text-xs text-red-600 hover:text-red-800"
                    :disabled="role.is_system"
                    @click="handleRemovePermission(perm.resource, perm.action)">
                    Remove
                  </button>
                </td>
              </tr>
              <tr v-if="role.permissions.length === 0">
                <td colspan="3" class="px-4 py-4 text-center text-gray-400">No permissions.</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="!role.is_system" class="mt-3 flex gap-2">
          <input v-model="newResource" placeholder="Resource (e.g. clients)"
            class="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none" />
          <input v-model="newAction" placeholder="Action (e.g. create)"
            class="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none" />
          <button class="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
            @click="handleAddPermission">
            Add
          </button>
        </div>
        <p v-if="newPermissionError" class="mt-1 text-xs text-red-600">{{ newPermissionError }}</p>
      </div>

      <!-- Users with this role -->
      <div>
        <h3 class="mb-2 text-sm font-semibold text-gray-700">Users with this Role</h3>
        <div class="overflow-x-auto rounded-lg border">
          <table class="min-w-full divide-y divide-gray-200 text-sm">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-2 text-left font-medium text-gray-600">Email</th>
                <th class="px-4 py-2 text-left font-medium text-gray-600">Name</th>
                <th class="px-4 py-2 text-center font-medium text-gray-600">Active</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr v-for="u in users" :key="u.id" class="cursor-pointer hover:bg-gray-50"
                @click="router.push({ name: 'admin-users-id', params: { id: u.id } })">
                <td class="px-4 py-2">{{ u.email }}</td>
                <td class="px-4 py-2 text-gray-600">{{ u.full_name || "—" }}</td>
                <td class="px-4 py-2 text-center">
                  <span class="inline-block h-2 w-2 rounded-full"
                    :class="u.is_active ? 'bg-green-500' : 'bg-red-400'" />
                </td>
              </tr>
              <tr v-if="users.length === 0">
                <td colspan="3" class="px-4 py-4 text-center text-gray-400">No users have this role.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <div v-else-if="error" class="py-8 text-center text-sm text-red-600">{{ error }}</div>
  </div>
</template>
