import type {
  AppResponse,
  BootstrapRequest,
  BootstrapStatusResponse,
  LoginRequest,
  LoginResponse,
  SetupCompleteRequest,
  TokenResponse,
  TOTPEnableResponse,
  TOTPVerifyRequest,
  UserResponse,
} from "../types/auth"
import { api } from "../composables/useApi"

export async function checkBootstrapStatus(): Promise<BootstrapStatusResponse> {
  const { data } = await api.get("/api/auth/bootstrap/status")
  return data
}

export async function bootstrap(body: BootstrapRequest): Promise<LoginResponse> {
  const { data } = await api.post("/api/auth/bootstrap", body)
  return data
}

export async function login(body: LoginRequest): Promise<LoginResponse> {
  const { data } = await api.post("/api/auth/login", body)
  return data
}

export async function loginTotp(sessionToken: string, totpCode: string): Promise<TokenResponse> {
  const { data } = await api.post("/api/auth/login/totp", {
    session_token: sessionToken,
    totp_code: totpCode,
  })
  return data
}

export async function recoverWithBackupCode(
  sessionToken: string,
  backupCode: string,
): Promise<{ setup_token: string; recovery: boolean }> {
  const { data } = await api.post("/api/auth/recovery/backup-code", {
    session_token: sessionToken,
    backup_code: backupCode,
  })
  return data
}

export async function setupComplete(body: SetupCompleteRequest, setupToken: string): Promise<TokenResponse> {
  const { data } = await api.post("/api/auth/setup-complete", body, {
    headers: { Authorization: `Bearer ${setupToken}` },
  })
  return data
}

export async function totpEnable(setupToken: string): Promise<TOTPEnableResponse> {
  const { data } = await api.post("/api/auth/totp/enable", {}, {
    headers: { Authorization: `Bearer ${setupToken}` },
  })
  return data
}

export async function totpVerify(body: TOTPVerifyRequest, setupToken: string): Promise<void> {
  await api.post("/api/auth/totp/verify", body, {
    headers: { Authorization: `Bearer ${setupToken}` },
  })
}

export async function refreshTokens(refreshToken: string): Promise<TokenResponse> {
  const { data } = await api.post("/api/auth/refresh", { refresh_token: refreshToken })
  return data
}

export async function logout(refreshToken: string): Promise<void> {
  await api.post("/api/auth/logout", { refresh_token: refreshToken })
}

export async function logoutAll(): Promise<void> {
  await api.post("/api/auth/logout-all")
}

export async function getMyApps(): Promise<AppResponse[]> {
  const { data } = await api.get("/api/auth/apps")
  return data
}

export async function generateBackupCodes(setupToken: string): Promise<string[]> {
  const { data } = await api.post("/api/auth/totp/backup-codes", {}, {
    headers: { Authorization: `Bearer ${setupToken}` },
  })
  return data.backup_codes
}

export async function me(): Promise<UserResponse> {
  const { data } = await api.get("/api/auth/me")
  return data
}

export async function forgotPassword(email: string): Promise<void> {
  await api.post("/api/auth/forgot-password", { email })
}

export async function resetPassword(token: string, newPassword: string): Promise<void> {
  await api.post("/api/auth/reset-password", { token, new_password: newPassword })
}
