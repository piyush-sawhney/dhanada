<script setup lang="ts">
import { onMounted, shallowRef } from "vue"
import { useRoute, useRouter } from "vue-router"
import { api } from "../composables/useApi"

const route = useRoute()
const router = useRouter()

const loading = shallowRef(true)
const verified = shallowRef(false)
const error = shallowRef("")

onMounted(async () => {
  const token = route.query.token as string | undefined
  if (!token) {
    error.value = "Invalid verification link: missing token."
    loading.value = false
    return
  }

  try {
    const { data } = await api.get("/api/auth/verify-email", { params: { token } })
    verified.value = data.verified
  } catch (err: any) {
    error.value = err.response?.data?.detail ?? "This verification link has expired or is invalid."
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-gray-50 px-4">
    <div class="w-full max-w-md rounded-xl bg-white p-8 text-center shadow-lg">
      <template v-if="loading">
        <div class="mx-auto flex h-16 w-16 items-center justify-center">
          <svg class="h-8 w-8 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>
      </template>

      <template v-else-if="verified">
        <div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
          <svg class="h-8 w-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h1 class="mb-2 text-xl font-semibold text-gray-900">Email Verified</h1>
        <p class="mb-6 text-sm text-gray-600">Your email address has been verified successfully.</p>
        <button class="rounded-lg bg-blue-600 px-6 py-2 text-sm font-semibold text-white hover:bg-blue-700"
          @click="router.push({ name: 'login' })">
          Go to Login
        </button>
      </template>

      <template v-else>
        <div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-100">
          <svg class="h-8 w-8 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </div>
        <h1 class="mb-2 text-xl font-semibold text-gray-900">Verification Failed</h1>
        <p class="mb-6 text-sm text-red-700">{{ error }}</p>
        <button class="rounded-lg bg-blue-600 px-6 py-2 text-sm font-semibold text-white hover:bg-blue-700"
          @click="router.push({ name: 'login' })">
          Back to Login
        </button>
      </template>
    </div>
  </div>
</template>
