<script setup lang="ts">
import { shallowRef } from "vue"
import { useRouter } from "vue-router"
import { useAuthStore } from "../stores/auth"

const router = useRouter()
const store = useAuthStore()

const email = shallowRef("")
const password = shallowRef("")
const fullName = shallowRef("")
const error = shallowRef("")
const loading = shallowRef(false)

async function handleSubmit() {
  error.value = ""
  loading.value = true

  try {
    const result = await store.bootstrap(email.value, password.value, fullName.value || undefined)

    if (result.type === "setup_required") {
      router.push({ name: "setup" })
    } else if (result.type === "success") {
      router.push({ name: "dashboard" })
    }
  } catch (err: any) {
    error.value = err.response?.data?.detail ?? "An unexpected error occurred"
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <form @submit.prevent="handleSubmit" class="space-y-5">
    <h2 class="text-xl font-semibold text-gray-900">Setup Dhanada</h2>
    <p class="text-sm text-gray-500">Create the first superuser account</p>

    <div v-if="error" class="rounded-lg bg-red-50 p-3 text-sm text-red-700">{{ error }}</div>

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
      <label for="fullName" class="block text-sm font-medium text-gray-700">Full Name (optional)</label>
      <input
        id="fullName"
        v-model="fullName"
        type="text"
        autocomplete="name"
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
        minlength="8"
        autocomplete="new-password"
        class="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-200 focus:outline-none"
      />
    </div>

    <button
      type="submit"
      :disabled="loading"
      class="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {{ loading ? "Creating..." : "Create Superuser" }}
    </button>
  </form>
</template>
