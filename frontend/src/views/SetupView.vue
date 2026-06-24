<script setup lang="ts">
import { shallowRef, onMounted } from "vue"
import { useRouter } from "vue-router"
import { useAuthStore } from "../stores/auth"
import { totpEnable, totpVerify } from "../api/auth"
import TOTPInput from "../components/TOTPInput.vue"
import QRCode from "qrcode"

const router = useRouter()
const store = useAuthStore()

type Step = "qr" | "verify"
const step = shallowRef<Step>("qr")
const qrDataUrl = shallowRef("")
const secret = shallowRef("")
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
    await completeSetup()
  } catch (err: any) {
    error.value = err.response?.data?.detail ?? "Invalid code. Try again."
    totpCode.value = ""
  } finally {
    loading.value = false
  }
}

async function completeSetup() {
  try {
    await store.completeSetup()
    router.push({ name: "dashboard" })
  } catch (err: any) {
    error.value = err.response?.data?.detail ?? "Failed to complete setup"
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
