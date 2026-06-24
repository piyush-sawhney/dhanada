<script setup lang="ts">
import { useAuthStore } from "../stores/auth"
import { useRouter, useRoute } from "vue-router"

const store = useAuthStore()
const router = useRouter()
const route = useRoute()

const isAdmin = () => route.path.startsWith("/admin")

async function handleLogout() {
  await store.logout()
  router.push({ name: "login" })
}
</script>

<template>
  <div class="flex min-h-screen flex-col">
    <header class="flex items-center justify-between border-b bg-white px-6 py-3">
      <span class="text-lg font-bold text-gray-900">Dhanada</span>
      <div class="flex items-center gap-4">
        <router-link
          v-if="store.user?.is_superuser"
          :to="{ name: 'admin-users' }"
          class="rounded-md px-3 py-1.5 text-sm font-medium transition"
          :class="isAdmin() ? 'bg-blue-100 text-blue-700' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'"
        >
          Admin
        </router-link>
        <span class="text-sm text-gray-600">{{ store.user?.email }}</span>
        <button
          class="rounded-md bg-gray-100 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-200"
          @click="handleLogout"
        >
          Logout
        </button>
      </div>
    </header>
    <main class="flex-1 p-6">
      <slot />
    </main>
  </div>
</template>
