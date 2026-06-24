<script setup lang="ts">
import { shallowRef, ref, onMounted } from "vue"
import { useRouter } from "vue-router"
import { useAuthStore } from "../stores/auth"
import { totpEnable, totpVerify } from "../api/auth"
import TOTPInput from "../components/TOTPInput.vue"
import QRCode from "qrcode"

const router = useRouter()
const store = useAuthStore()

type Step = "qr" | "backup-codes" | "verify"
const step = shallowRef<Step>("qr")
const qrDataUrl = shallowRef("")
const secret = shallowRef("")
const backupCodes = ref<string[] | null>(null)
const totpCode = shallowRef("")
const error = shallowRef("")
const loading = shallowRef(false)
const codesDownloaded = shallowRef(false)

const isRecovery = store.recoveryMode

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
    backupCodes.value = response.backup_codes ?? null
  } catch (err: any) {
    error.value = err.response?.data?.detail ?? "Failed to setup authenticator"
  } finally {
    loading.value = false
  }
})

function downloadCodes() {
  if (!backupCodes.value) return
  const text = backupCodes.value
    .map((code, i) => `${i + 1}. ${code}`)
    .join("\n")
  const blob = new Blob([text], { type: "text/plain" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = "dhanada-backup-codes.txt"
  a.click()
  URL.revokeObjectURL(url)
  codesDownloaded.value = true
}

async function verifyTOTP() {
  error.value = ""
  loading.value = true

  try {
    await totpVerify({ token: totpCode.value }, store.setupToken!)
    if (backupCodes.value && backupCodes.value.length > 0) {
      step.value = "backup-codes"
    } else {
      await completeSetup()
    }
  } catch (err: any) {
    error.value = err.response?.data?.detail ?? "Invalid code. Try again."
    totpCode.value = ""
  } finally {
    loading.value = false
  }
}

async function completeSetup() {
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

    <template v-else-if="step === 'backup-codes'">
      <div v-if="isRecovery" class="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
        Your old backup codes have been invalidated. These are your new backup codes —
        save them before continuing. You'll need them if you ever lose access to your
        authenticator app again.
      </div>
      <p v-else class="text-sm text-gray-500">
        Save these backup codes in a secure place. You'll need them if you ever lose
        access to your authenticator app.
      </p>
      <div class="rounded-lg border bg-gray-50 p-4 font-mono text-sm">
        <div v-for="(code, i) in backupCodes" :key="i" class="py-1">
          {{ i + 1 }}. {{ code }}
        </div>
      </div>
      <button
        class="w-full rounded-lg border bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        @click="downloadCodes"
      >
        {{ codesDownloaded ? "Downloaded!" : "Download codes" }}
      </button>
      <button
        class="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="loading || !codesDownloaded"
        @click="completeSetup"
      >
        {{ loading ? "Finishing setup..." : "I've saved my backup codes" }}
      </button>
    </template>

    <template v-else>
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
  </div>
</template>
