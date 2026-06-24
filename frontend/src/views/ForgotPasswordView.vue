<script setup lang="ts">
import { shallowRef } from "vue"
import { forgotPassword as apiForgotPassword } from "../api/auth"

const email = shallowRef("")
const sent = shallowRef(false)
const error = shallowRef("")
const loading = shallowRef(false)

async function handleSubmit() {
  error.value = ""
  loading.value = true

  try {
    await apiForgotPassword(email.value)
    sent.value = true
  } catch {
    sent.value = true
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="space-y-5">
    <template v-if="sent">
      <h2 class="text-xl font-semibold text-gray-900">Check your email</h2>
      <p class="text-sm text-gray-500">
        If an account with that email exists, we've sent a password reset link.
      </p>
      <router-link
        to="/login"
        class="block text-center text-sm text-blue-600 hover:text-blue-700"
      >
        Back to login
      </router-link>
    </template>

    <template v-else>
      <h2 class="text-xl font-semibold text-gray-900">Forgot password</h2>
      <p class="text-sm text-gray-500">
        Enter your email and we'll send you a reset link.
      </p>

      <div v-if="error" class="rounded-lg bg-red-50 p-3 text-sm text-red-700">{{ error }}</div>

      <form @submit.prevent="handleSubmit" class="space-y-5">
        <div>
          <label for="email" class="block text-sm font-medium text-gray-700">Email</label>
          <input
            id="email"
            v-model="email"
            type="email"
            required
            autocomplete="email"
            class="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-200 focus:outline-none"
          />
        </div>

        <button
          type="submit"
          :disabled="loading"
          class="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {{ loading ? "Sending..." : "Send reset link" }}
        </button>

        <div class="text-center">
          <router-link to="/login" class="text-sm text-gray-500 hover:text-gray-700">
            Back to login
          </router-link>
        </div>
      </form>
    </template>
  </div>
</template>
