<script setup lang="ts">
import { useRoute } from "vue-router"

const route = useRoute()

const tabs = [
  { name: "Users", path: "/admin/users", to: { name: "admin-users" } },
  { name: "Roles", path: "/admin/roles", to: { name: "admin-roles" } },
]
</script>

<template>
  <nav class="mb-6 flex gap-1 border-b">
    <router-link
      v-for="tab in tabs"
      :key="tab.path"
      :to="tab.to"
      class="rounded-t-lg px-4 py-2 text-sm font-medium transition"
      :class="
        route.path.startsWith(tab.path)
          ? 'border-b-2 border-blue-600 text-blue-700'
          : 'text-gray-500 hover:text-gray-700'
      "
    >
      {{ tab.name }}
    </router-link>
  </nav>
</template>
