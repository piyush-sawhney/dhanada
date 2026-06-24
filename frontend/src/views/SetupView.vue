<script setup lang="ts">
import { shallowRef, onMounted } from "vue"
import { useRouter } from "vue-router"
import { useAuthStore } from "../stores/auth"
import { totpEnable, totpVerify, generateBackupCodes } from "../api/auth"
import TOTPInput from "../components/TOTPInput.vue"
import QRCode from "qrcode"

const router = useRouter()
const store = useAuthStore()

type Step = "qr" | "verify" | "backup-codes"
const step = shallowRef<Step>("qr")
const qrDataUrl = shallowRef("")
const secret = shallowRef("")
const backupCodes = shallowRef<string[]>([])
const backupCodesAcknowledged = shallowRef(false)
const totpCode = shallowRef("")
const error = shallowRef("")
const loading = shallowRef(false)

onMounted(async () => {
  if (!store.setupToken) {
    router.push({ name: "login" })
    return
  }

  loading.value = true
  try {
    const response = await totpEnable(store.setupToken)
    qrDataUrl.value = await QRCode.toDataURL(response.provisioning_uri, {
      width: 256,
      margin: 2,
    })
    secret.value = response.secret
  } catch (err: any) {
    error.value = err.response?.data?.detail ?? "Failed to setup authenticator"
  } finally {
    loading.value = false
  }
})

async function verifyTOTP() {
  error.value = ""
  loading.value = true

  try {
    await totpVerify({ token: totpCode.value }, store.setupToken!)
    backupCodes.value = await generateBackupCodes(store.setupToken!)
    step.value = "backup-codes"
  } catch (err: any) {
    error.value = err.response?.data?.detail ?? "Invalid code. Try again."
    totpCode.value = ""
  } finally {
    loading.value = false
  }
}

function downloadBackupCodes() {
  const content = backupCodes.value.join("\n")
  const blob = new Blob([content], { type: "text/plain" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = "dhanada-backup-codes.txt"
  a.click()
  URL.revokeObjectURL(url)
}

async function completeSetup() {
  error.value = ""
  loading.value = true

  try {
    await store.completeSetup()
    router.push({ name: "dashboard" })
  } catch (err: any) {
    error.value = err.response?.data?.detail ?? "Failed to complete setup"
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="space-y-5">
    <h2 class="text-xl font-semibold text-gray-900">Account Setup</h2>

    <div v-if="error" class="rounded-lg bg-red-50 p-3 text-sm text-red-700">{{ error }}</div>

    <template v-if="step === 'qr'">
      <p class="text-sm text-gray-500">
        Scan this QR code with your authenticator app (Google Authenticator, Authy, etc.)
      </p>
      <div class="flex justify-center">
        <div v-if="qrDataUrl" class="rounded-lg border p-2">
          <img :src="qrDataUrl" alt="TOTP QR Code" class="h-64 w-64" />
        </div>
        <div v-else class="flex h-64 w-64 items-center justify-center rounded-lg bg-gray-100 text-sm text-gray-400">
          {{ loading ? "Generating QR code..." : "No QR code available" }}
        </div>
      </div>
      <p v-if="secret" class="text-center text-xs text-gray-400">
        Or enter this key manually: <code class="font-mono">{{ secret }}</code>
      </p>
      <button
        class="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700"
        :disabled="!qrDataUrl"
        @click="step = 'verify'"
      >
        I've scanned the code
      </button>
    </template>

    <template v-else-if="step === 'verify'">
      <p class="text-sm text-gray-500">Enter the 6-digit code from your authenticator app</p>
      <form @submit.prevent="verifyTOTP" class="space-y-5">
        <TOTPInput v-model="totpCode" />
        <button
          type="submit"
          :disabled="loading || totpCode.length !== 6"
          class="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {{ loading ? "Verifying..." : "Verify" }}
        </button>
      </form>
    </template>

    <template v-else-if="step === 'backup-codes'">
      <p class="text-sm text-gray-500">
        Save these backup codes in a safe place. You can use each code once to log in if you lose access to your authenticator app.
      </p>
      <div class="rounded-lg border bg-gray-50 p-4 font-mono text-xs">
        <div v-for="(code, i) in backupCodes" :key="i" class="py-0.5">{{ code }}</div>
      </div>
      <div class="flex gap-3">
        <button
          class="flex-1 rounded-lg border border-gray-300 px-4 py-2.5 text-sm font-semibold text-gray-700 hover:bg-gray-50"
          @click="downloadBackupCodes"
        >
          Download
        </button>
      </div>
      <label class="flex items-start gap-2 text-sm text-gray-600">
        <input
          v-model="backupCodesAcknowledged"
          type="checkbox"
          class="mt-0.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
        />
        <span>I have saved my backup codes</span>
      </label>
      <button
        :disabled="!backupCodesAcknowledged || loading"
        class="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        @click="completeSetup"
      >
        {{ loading ? "Completing..." : "Continue to Dashboard" }}
      </button>
    </template>
  </div>
</template>
