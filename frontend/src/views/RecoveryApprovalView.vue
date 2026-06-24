<script setup lang="ts">
import { onMounted, shallowRef } from "vue"
import { useRoute, useRouter } from "vue-router"
import { approveRecovery } from "../api/auth"
import { useAuthStore } from "../stores/auth"
import { setSetupToken } from "../utils/token"

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const error = shallowRef("")

onMounted(async () => {
  const token = route.query.token as string | undefined
  if (!token) {
    error.value = "Invalid recovery link: missing token."
    return
  }

  try {
    const { setup_token } = await approveRecovery(token)
    auth.setupToken = setup_token as any
    setSetupToken(setup_token)
    router.replace({ name: "setup" })
  } catch {
    error.value = "This recovery link has expired or is invalid. Please log in again."
  }
})
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-gray-50 px-4">
    <div class="w-full max-w-md rounded-xl bg-white p-8 text-center shadow-lg">
      <div v-if="error" class="mb-4 rounded-lg bg-red-50 p-4 text-sm text-red-700">{{ error }}</div>
      <div v-else class="mx-auto flex h-16 w-16 items-center justify-center">
        <svg class="h-8 w-8 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      </div>
    </div>
  </div>
</template>
