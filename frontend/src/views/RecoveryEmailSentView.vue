<script setup lang="ts">
import { useRouter } from "vue-router"

const router = useRouter()
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-gray-50 px-4">
    <div class="w-full max-w-md rounded-xl bg-white p-8 text-center shadow-lg">
      <div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-blue-100">
        <svg class="h-8 w-8 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
      </div>
      <h1 class="mb-2 text-xl font-semibold text-gray-900">Recovery Email Sent</h1>
      <p class="mb-6 text-sm text-gray-600">
        A recovery email has been sent to your email address. Check your inbox
        and click the link to approve setting up a new authenticator.
      </p>
      <p class="mb-6 text-xs text-gray-400">
        The link expires in 15 minutes. If you did not request this, you can
        safely ignore the email.
      </p>
      <button class="rounded-lg bg-blue-600 px-6 py-2 text-sm font-semibold text-white hover:bg-blue-700"
        @click="router.push({ name: 'login' })">
        Back to Login
      </button>
    </div>
  </div>
</template>
