<script setup lang="ts">
import { onMounted } from "vue"
import { useRouter } from "vue-router"
import { useAuthStore } from "../stores/auth"

const router = useRouter()
const store = useAuthStore()

onMounted(async () => {
  if (store.userApps.length === 0) {
    await store.fetchApps()
  }
})

function openApp(slug: string) {
  router.push(`/${slug}/clients`)
}
</script>

<template>
  <div class="space-y-6">
    <h2 class="text-xl font-semibold text-gray-900">
      Welcome{{ store.user?.full_name ? `, ${store.user.full_name}` : "" }}
    </h2>
    <p class="text-sm text-gray-500">Select an application to get started.</p>

    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <button
        v-for="app in store.userApps"
        :key="app.slug"
        class="rounded-lg border border-gray-200 bg-white p-6 text-left shadow-sm transition hover:border-blue-300 hover:shadow-md"
        @click="openApp(app.slug)"
      >
        <h3 class="text-lg font-semibold text-gray-900">{{ app.name }}</h3>
        <p class="mt-1 text-sm text-gray-500">{{ app.slug }}</p>
      </button>
    </div>
  </div>
</template>
