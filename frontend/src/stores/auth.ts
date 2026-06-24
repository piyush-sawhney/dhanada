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
  const sessionToken = shallowRef<string | null>(null)
  const recoveryMode = shallowRef(false)
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
    clearSetupToken()
    setupToken.value = null
    sessionToken.value = null
    recoveryMode.value = false
    bootstrapChecked.value = true
  }

  async function login(email: string, password: string) {
    const response = await authApi.login({ email, password })

    if ("setup_token" in response) {
      setupToken.value = response.setup_token
      setSetupToken(response.setup_token)
      recoveryMode.value = !!response.recovery
      return { type: "setup_required" as const, recovery: !!response.recovery }
    }

    if ("session_token" in response) {
      sessionToken.value = response.session_token
      return { type: "session_issued" as const, sessionToken: response.session_token }
    }

    return { type: "error" as const }
  }

  async function loginTotp(totpCode: string) {
    if (!sessionToken.value) throw new Error("No session token")
    const tokens = await authApi.loginTotp(sessionToken.value, totpCode)
    setTokens(tokens)
    await fetchUser()
    return { type: "success" as const }
  }

  async function recoverWithBackupCode(backupCode: string) {
    if (!sessionToken.value) throw new Error("No session token")
    const response = await authApi.recoverWithBackupCode(sessionToken.value, backupCode)
    setupToken.value = response.setup_token
    setSetupToken(response.setup_token)
    recoveryMode.value = response.recovery
    sessionToken.value = null
    return { type: "setup_required" as const, recovery: response.recovery }
  }

  async function bootstrap(email: string, password: string, fullName?: string) {
    const response = await authApi.bootstrap({ email, password, full_name: fullName })

    if ("setup_token" in response) {
      setupToken.value = response.setup_token
      setSetupToken(response.setup_token)
      recoveryMode.value = false
      return { type: "setup_required" as const }
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
    recoveryMode.value = false
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
      sessionToken.value = null
      recoveryMode.value = false
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

  function clearSession() {
    sessionToken.value = null
  }

  return {
    user,
    userApps,
    accessToken,
    setupToken,
    sessionToken,
    recoveryMode,
    bootstrapChecked,
    isAuthenticated,
    isSetupRequired,
    fetchUser,
    fetchApps,
    login,
    loginTotp,
    recoverWithBackupCode,
    bootstrap,
    completeSetup,
    logout,
    checkAuth,
    setTokens,
    clearSession,
  }
})
