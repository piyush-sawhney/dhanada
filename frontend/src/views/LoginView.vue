<script setup lang="ts">
import { shallowRef } from "vue"
import { useRouter } from "vue-router"
import { useAuthStore } from "../stores/auth"
import TOTPInput from "../components/TOTPInput.vue"

const router = useRouter()
const store = useAuthStore()

const step = shallowRef<"credentials" | "totp">("credentials")
const email = shallowRef("")
const password = shallowRef("")
const totpToken = shallowRef("")
const error = shallowRef("")
const loading = shallowRef(false)

async function submitCredentials() {
  error.value = ""
  loading.value = true

  try {
    const result = await store.login(email.value, password.value)

    if (result.type === "setup_required") {
      router.push({ name: "setup" })
    } else if (result.type === "success") {
      router.push({ name: "dashboard" })
    }
  } catch (err: any) {
    const status = err.response?.status
    const detail = err.response?.data?.detail ?? ""

    if (status === 403 && detail.includes("TOTP")) {
      step.value = "totp"
    } else if (status === 429) {
      error.value = detail || "Too many attempts. Please try again later."
    } else {
      error.value = detail || "Invalid email or password"
    }
  } finally {
    loading.value = false
  }
}

async function submitTOTP() {
  error.value = ""
  loading.value = true

  try {
    const result = await store.login(email.value, password.value, totpToken.value)

    if (result.type === "success") {
      router.push({ name: "dashboard" })
    } else {
      error.value = "Invalid code. Try again."
      totpToken.value = ""
    }
  } catch (err: any) {
    error.value = err.response?.data?.detail ?? "Invalid code. Try again."
    totpToken.value = ""
  } finally {
    loading.value = false
  }
}

function backToCredentials() {
  step.value = "credentials"
  error.value = ""
}
</script>

<template>
  <form @submit.prevent="step === 'credentials' ? submitCredentials() : submitTOTP()" class="space-y-5">
    <h2 class="text-xl font-semibold text-gray-900">
      {{ step === "credentials" ? "Sign in" : "Two-factor authentication" }}
    </h2>
    <p class="text-sm text-gray-500">
      {{ step === "credentials" ? "Enter your credentials" : "Enter the code from your authenticator app" }}
    </p>

    <div v-if="error" class="rounded-lg bg-red-50 p-3 text-sm text-red-700">{{ error }}</div>

    <template v-if="step === 'credentials'">
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

      <div>
        <label for="password" class="block text-sm font-medium text-gray-700">Password</label>
        <input
          id="password"
          v-model="password"
          type="password"
          required
          autocomplete="current-password"
          class="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-200 focus:outline-none"
        />
      </div>

      <button
        type="submit"
        :disabled="loading"
        class="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {{ loading ? "Verifying..." : "Continue" }}
      </button>

      <div class="text-center">
        <router-link to="/forgot-password" class="text-sm text-blue-600 hover:text-blue-700">
          Forgot password?
        </router-link>
      </div>
    </template>

    <template v-else>
      <TOTPInput v-model="totpToken" />

      <button
        type="submit"
        :disabled="loading || totpToken.length !== 6"
        class="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {{ loading ? "Verifying..." : "Verify" }}
      </button>

      <button
        type="button"
        class="w-full text-sm text-gray-500 hover:text-gray-700"
        @click="backToCredentials"
      >
        Back to login
      </button>
    </template>
  </form>
</template>
