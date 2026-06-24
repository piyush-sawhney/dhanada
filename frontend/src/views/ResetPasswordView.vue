<script setup lang="ts">
import { shallowRef, onMounted } from "vue"
import { useRoute } from "vue-router"
import { resetPassword as apiResetPassword } from "../api/auth"

const route = useRoute()

const token = shallowRef("")
const newPassword = shallowRef("")
const error = shallowRef("")
const success = shallowRef(false)
const loading = shallowRef(false)

onMounted(() => {
  token.value = (route.query.token as string) ?? ""
  if (!token.value) {
    error.value = "Invalid or missing reset token"
  }
})

async function handleSubmit() {
  error.value = ""
  loading.value = true

  try {
    await apiResetPassword(token.value, newPassword.value)
    success.value = true
  } catch (err: any) {
    error.value = err.response?.data?.detail ?? "Failed to reset password. The link may have expired."
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="space-y-5">
    <template v-if="success">
      <h2 class="text-xl font-semibold text-gray-900">Password reset</h2>
      <p class="text-sm text-gray-500">Your password has been reset successfully.</p>
      <router-link
        to="/login"
        class="block text-center text-sm font-semibold text-blue-600 hover:text-blue-700"
      >
        Sign in
      </router-link>
    </template>

    <template v-else-if="!token">
      <h2 class="text-xl font-semibold text-gray-900">Invalid link</h2>
      <p class="text-sm text-red-600">{{ error }}</p>
      <router-link
        to="/forgot-password"
        class="block text-center text-sm text-blue-600 hover:text-blue-700"
      >
        Request a new reset link
      </router-link>
    </template>

    <template v-else>
      <h2 class="text-xl font-semibold text-gray-900">Reset password</h2>
      <p class="text-sm text-gray-500">Enter your new password.</p>

      <div v-if="error" class="rounded-lg bg-red-50 p-3 text-sm text-red-700">{{ error }}</div>

      <form @submit.prevent="handleSubmit" class="space-y-5">
        <div>
          <label for="newPassword" class="block text-sm font-medium text-gray-700">New Password</label>
          <input
            id="newPassword"
            v-model="newPassword"
            type="password"
            required
            minlength="8"
            autocomplete="new-password"
            class="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-200 focus:outline-none"
          />
        </div>

        <button
          type="submit"
          :disabled="loading || newPassword.length < 8"
          class="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {{ loading ? "Resetting..." : "Reset password" }}
        </button>
      </form>
    </template>
  </div>
</template>
