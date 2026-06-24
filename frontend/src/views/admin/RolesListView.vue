<script setup lang="ts">
import { onMounted } from "vue"
import { useRouter } from "vue-router"
import { useAdminStore } from "../../stores/admin"
import { deleteRole } from "../../api/admin"
import AdminNav from "../../components/AdminNav.vue"

const router = useRouter()
const admin = useAdminStore()

onMounted(() => {
  if (admin.roles.length === 0) admin.fetchRoles()
})

async function handleDelete(roleId: string, name: string) {
  if (!confirm(`Delete role "${name}"?`)) return
  const ok = await deleteRole(roleId)
  if (ok) admin.fetchRoles()
}
</script>

<template>
  <div>
    <AdminNav />
    <div class="mb-4 flex items-center justify-between">
      <h2 class="text-xl font-semibold text-gray-900">Roles</h2>
      <router-link
        :to="{ name: 'admin-roles-new' }"
        class="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
      >
        New Role
      </router-link>
    </div>

    <div class="overflow-x-auto rounded-lg border">
      <table class="min-w-full divide-y divide-gray-200 text-sm">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-4 py-3 text-left font-medium text-gray-600">Name</th>
            <th class="px-4 py-3 text-left font-medium text-gray-600">Description</th>
            <th class="px-4 py-3 text-center font-medium text-gray-600">System</th>
            <th class="px-4 py-3 text-center font-medium text-gray-600">Permissions</th>
            <th class="px-4 py-3 text-right font-medium text-gray-600">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          <tr
            v-for="role in admin.roles"
            :key="role.id"
            class="cursor-pointer hover:bg-gray-50"
            @click="router.push({ name: 'admin-roles-name', params: { name: role.name } })"
          >
            <td class="px-4 py-3 font-medium">{{ role.name }}</td>
            <td class="px-4 py-3 text-gray-600">{{ role.description || "—" }}</td>
            <td class="px-4 py-3 text-center">
              <span
                class="inline-block h-2 w-2 rounded-full"
                :class="role.is_system ? 'bg-amber-400' : 'bg-gray-300'"
              />
            </td>
            <td class="px-4 py-3 text-center">{{ role.permissions.length }}</td>
            <td class="px-4 py-3 text-right">
              <button
                class="text-red-600 hover:text-red-800"
                :disabled="role.is_system"
                @click.stop="handleDelete(role.id, role.name)"
              >
                Delete
              </button>
            </td>
          </tr>
          <tr v-if="admin.roles.length === 0">
            <td colspan="5" class="px-4 py-8 text-center text-gray-400">No roles found.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
