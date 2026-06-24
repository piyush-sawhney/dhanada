<script setup lang="ts">
import { onMounted } from "vue"
import { useRouter } from "vue-router"
import { useAdminStore } from "../../stores/admin"
import { deleteUser } from "../../api/admin"
import AdminNav from "../../components/AdminNav.vue"

const router = useRouter()
const admin = useAdminStore()

onMounted(() => {
  if (admin.users.length === 0) admin.fetchUsers()
})

async function handleDelete(id: string, email: string) {
  if (!confirm(`Delete user "${email}"?`)) return
  await deleteUser(id)
  admin.fetchUsers()
}

function totalPages() {
  return Math.ceil(admin.total / admin.perPage)
}

function pages(): number[] {
  const tp = totalPages()
  const current = admin.page
  const start = Math.max(1, current - 2)
  const end = Math.min(tp, current + 2)
  const p: number[] = []
  for (let i = start; i <= end; i++) p.push(i)
  return p
}
</script>

<template>
  <div>
    <AdminNav />
    <div class="mb-4 flex items-center justify-between">
      <h2 class="text-xl font-semibold text-gray-900">Users</h2>
      <router-link
        :to="{ name: 'admin-users-new' }"
        class="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
      >
        New User
      </router-link>
    </div>

    <div class="mb-4">
      <input
        v-model="admin.search"
        type="text"
        placeholder="Search by email or name..."
        class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-200 focus:outline-none"
        @input="admin.setSearch(admin.search)"
      />
    </div>

    <div class="overflow-x-auto rounded-lg border">
      <table class="min-w-full divide-y divide-gray-200 text-sm">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-4 py-3 text-left font-medium text-gray-600">Email</th>
            <th class="px-4 py-3 text-left font-medium text-gray-600">Name</th>
            <th class="px-4 py-3 text-center font-medium text-gray-600">Active</th>
            <th class="px-4 py-3 text-center font-medium text-gray-600">Superuser</th>
            <th class="px-4 py-3 text-left font-medium text-gray-600">Roles</th>
            <th class="px-4 py-3 text-right font-medium text-gray-600">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          <tr
            v-for="user in admin.users"
            :key="user.id"
            class="cursor-pointer hover:bg-gray-50"
            @click="router.push({ name: 'admin-users-id', params: { id: user.id } })"
          >
            <td class="px-4 py-3">{{ user.email }}</td>
            <td class="px-4 py-3 text-gray-600">{{ user.full_name || "—" }}</td>
            <td class="px-4 py-3 text-center">
              <span
                class="inline-block h-2 w-2 rounded-full"
                :class="user.is_active ? 'bg-green-500' : 'bg-red-400'"
              />
            </td>
            <td class="px-4 py-3 text-center">
              <span
                class="inline-block h-2 w-2 rounded-full"
                :class="user.is_superuser ? 'bg-green-500' : 'bg-gray-300'"
              />
            </td>
            <td class="px-4 py-3">
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="role in user.roles"
                  :key="role"
                  class="rounded bg-blue-100 px-2 py-0.5 text-xs text-blue-700"
                >
                  {{ role }}
                </span>
                <span v-if="user.roles.length === 0" class="text-gray-400">—</span>
              </div>
            </td>
            <td class="px-4 py-3 text-right">
              <button
                class="text-red-600 hover:text-red-800"
                @click.stop="handleDelete(user.id, user.email)"
              >
                Delete
              </button>
            </td>
          </tr>
          <tr v-if="admin.users.length === 0">
            <td colspan="6" class="px-4 py-8 text-center text-gray-400">No users found.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="totalPages() > 1" class="mt-4 flex items-center justify-center gap-2">
      <button
        :disabled="admin.page <= 1"
        class="rounded px-3 py-1 text-sm disabled:opacity-40"
        @click="admin.setPage(admin.page - 1)"
      >
        « Prev
      </button>
      <button
        v-for="p in pages()"
        :key="p"
        class="rounded px-3 py-1 text-sm"
        :class="p === admin.page ? 'bg-blue-600 text-white' : 'bg-gray-100 hover:bg-gray-200'"
        @click="admin.setPage(p)"
      >
        {{ p }}
      </button>
      <button
        :disabled="admin.page >= totalPages()"
        class="rounded px-3 py-1 text-sm disabled:opacity-40"
        @click="admin.setPage(admin.page + 1)"
      >
        Next »
      </button>
    </div>
  </div>
</template>
