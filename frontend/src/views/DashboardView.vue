<script setup lang="ts">
import { useAuthStore } from "../stores/auth"

const store = useAuthStore()
</script>

<template>
  <div>
    <h2 class="text-xl font-semibold text-gray-900">
      Welcome{{ store.user?.full_name ? `, ${store.user.full_name}` : "" }}
    </h2>
    <p class="mt-1 text-sm text-gray-500">You are signed in as <strong>{{ store.user?.email }}</strong></p>
  </div>
</template>
