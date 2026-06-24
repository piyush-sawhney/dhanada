import { defineStore } from "pinia"
import { ref, shallowRef, computed } from "vue"
import type { AppResponse, UserResponse } from "../types/auth"
import {
  getAccessToken, setAccessToken, setRefreshToken,
  getSetupToken, setSetupToken, clearSetupToken, clearTokens,
} from "../utils/token"
import * as authApi from "../api/auth"

export const useAuthStore = defineStore("auth", () => {
  const user = shallowRef<UserResponse | null>(null)
  const userApps = shallowRef<AppResponse[]>([])
  const accessToken = shallowRef<string | null>(getAccessToken())
  const setupToken = shallowRef<string | null>(getSetupToken())
  const bootstrapChecked = ref(false)

  const isAuthenticated = computed(() => !!accessToken.value)
  const isSetupRequired = computed(() => !!setupToken.value)

  async function fetchUser() {
    try {
      user.value = await authApi.me()
    } catch {
      user.value = null
      accessToken.value = null
      clearTokens()
    }
  }

  function setTokens(tokens: { access_token: string; refresh_token: string }) {
    accessToken.value = tokens.access_token
    setAccessToken(tokens.access_token)
    setRefreshToken(tokens.refresh_token)
    setupToken.value = null
    clearSetupToken()
    bootstrapChecked.value = true
  }

  async function login(email: string, password: string, totpToken?: string) {
    const response = await authApi.login({ email, password, totp_token: totpToken })

    if ("setup_token" in response) {
      setupToken.value = response.setup_token
      setSetupToken(response.setup_token)
      return { type: "setup_required" as const, token: response.setup_token }
    }

    if ("status" in response && response.status === "totp_required") {
      return { type: "totp_required" as const }
    }

    if ("access_token" in response) {
      setTokens(response)
      await fetchUser()
      return { type: "success" as const }
    }

    if ("status" in response && response.status === "recovery_email_sent") {
      return { type: "recovery_email_sent" as const }
    }

    return { type: "error" as const }
  }

  async function bootstrap(email: string, password: string, fullName?: string) {
    const response = await authApi.bootstrap({ email, password, full_name: fullName })

    if ("setup_token" in response) {
      setupToken.value = response.setup_token
      setSetupToken(response.setup_token)
      return { type: "setup_required" as const, token: response.setup_token }
    }

    if ("access_token" in response) {
      setTokens(response)
      await fetchUser()
      return { type: "success" as const }
    }

    return { type: "error" as const }
  }

  async function completeSetup(newPassword?: string) {
    if (!setupToken.value) throw new Error("No setup token")

    const tokens = await authApi.setupComplete({ new_password: newPassword }, setupToken.value)
    setTokens(tokens)
    await fetchUser()
  }

  async function logout() {
    try {
      await authApi.logoutAll()
    } catch {
    } finally {
      user.value = null
      accessToken.value = null
      clearTokens()
      bootstrapChecked.value = false
    }
  }

  async function fetchApps() {
    userApps.value = await authApi.getMyApps()
  }

  async function checkAuth() {
    if (accessToken.value) {
      await fetchUser()
    }
  }

  return {
    user,
    userApps,
    accessToken,
    setupToken,
    bootstrapChecked,
    isAuthenticated,
    isSetupRequired,
    fetchUser,
    fetchApps,
    login,
    bootstrap,
    completeSetup,
    logout,
    checkAuth,
    setTokens,
  }
})
