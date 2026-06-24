<script setup lang="ts">
import { shallowRef } from "vue"
import { useRouter } from "vue-router"
import { useAuthStore } from "../stores/auth"
import TOTPInput from "../components/TOTPInput.vue"

const router = useRouter()
const store = useAuthStore()

type Step = "credentials" | "totp" | "recovery"

const step = shallowRef<Step>("credentials")
const email = shallowRef("")
const password = shallowRef("")
const totpToken = shallowRef("")
const backupCode = shallowRef("")
const error = shallowRef("")
const loading = shallowRef(false)

async function submitCredentials() {
  error.value = ""
  loading.value = true

  try {
    const result = await store.login(email.value, password.value)

    if (result.type === "setup_required") {
      router.push({ name: "setup" })
    } else if (result.type === "session_issued") {
      step.value = "totp"
    } else {
      error.value = "Invalid email or password."
    }
  } catch (err: any) {
    const data = err.response?.data ?? {}
    const detail = data.detail ?? ""

    if (err.response?.status === 429) {
      const lockedUntil = data.locked_until
      if (lockedUntil) {
        const local = new Date(lockedUntil).toLocaleTimeString()
        error.value = `Account locked. Try again at ${local}.`
      } else {
        error.value = detail || "Too many attempts. Please try again later."
      }
    } else if (err.response?.status === 409) {
      error.value = detail || "Conflict."
    } else {
      error.value = detail || "Invalid email or password."
    }
  } finally {
    loading.value = false
  }
}

async function submitTOTP() {
  error.value = ""
  loading.value = true

  try {
    await store.loginTotp(totpToken.value)
    router.push({ name: "dashboard" })
  } catch (err: any) {
    error.value = err.response?.data?.detail ?? "Invalid code. Try again."
    totpToken.value = ""
  } finally {
    loading.value = false
  }
}

async function submitBackupCode() {
  error.value = ""
  loading.value = true

  try {
    await store.recoverWithBackupCode(backupCode.value)
    router.push({ name: "setup" })
  } catch (err: any) {
    error.value = err.response?.data?.detail ?? "Invalid backup code. Try again."
    backupCode.value = ""
  } finally {
    loading.value = false
  }
}

function showRecovery() {
  step.value = "recovery"
  error.value = ""
  backupCode.value = ""
}

function backToTotp() {
  step.value = "totp"
  error.value = ""
  backupCode.value = ""
}

function backToCredentials() {
  step.value = "credentials"
  error.value = ""
  store.clearSession()
}
</script>

<template>
  <form
    @submit.prevent="
      step === 'credentials'
        ? submitCredentials()
        : step === 'totp'
          ? submitTOTP()
          : submitBackupCode()
    "
    class="space-y-5"
  >
    <h2 class="text-xl font-semibold text-gray-900">
      <template v-if="step === 'credentials'">Sign in</template>
      <template v-else-if="step === 'totp'">Two-factor authentication</template>
      <template v-else>Recovery</template>
    </h2>

    <p class="text-sm text-gray-500">
      <template v-if="step === 'credentials'">Enter your credentials</template>
      <template v-else-if="step === 'totp'">Enter the code from your authenticator app</template>
      <template v-else>Enter one of your backup recovery codes</template>
    </p>

    <div v-if="error" class="rounded-lg bg-red-50 p-3 text-sm text-red-700">{{ error }}</div>

    <!-- Step 1: Credentials -->
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

    <!-- Step 2: TOTP Code -->
    <template v-else-if="step === 'totp'">
      <TOTPInput v-model="totpToken" />

      <button
        type="submit"
        :disabled="loading || totpToken.length !== 6"
        class="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {{ loading ? "Verifying..." : "Verify" }}
      </button>

      <div class="text-center">
        <button
          type="button"
          class="text-sm text-gray-500 hover:text-gray-700"
          @click="showRecovery"
        >
          Lost your authenticator?
        </button>
      </div>

      <button
        type="button"
        class="w-full text-sm text-gray-500 hover:text-gray-700"
        @click="backToCredentials"
      >
        Back to login
      </button>
    </template>

    <!-- Step 3: Backup Code Recovery -->
    <template v-else>
      <div>
        <label for="backup-code" class="block text-sm font-medium text-gray-700">
          Backup recovery code
        </label>
        <input
          id="backup-code"
          v-model="backupCode"
          type="text"
          required
          autocomplete="off"
          placeholder="Enter your 16-character backup code"
          class="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:border-blue-500 focus:ring-2 focus:ring-blue-200 focus:outline-none"
        />
      </div>

      <button
        type="submit"
        :disabled="loading || backupCode.length !== 16"
        class="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {{ loading ? "Verifying..." : "Recover account" }}
      </button>

      <button
        type="button"
        class="w-full text-sm text-gray-500 hover:text-gray-700"
        @click="backToTotp"
      >
        Back to authenticator code
      </button>
    </template>
  </form>
</template>
