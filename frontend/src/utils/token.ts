const ACCESS_TOKEN_KEY = "dhanada_access_token"
const REFRESH_TOKEN_KEY = "dhanada_refresh_token"
const SETUP_TOKEN_KEY = "dhanada_setup_token"

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function setAccessToken(token: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, token)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

export function setRefreshToken(token: string): void {
  localStorage.setItem(REFRESH_TOKEN_KEY, token)
}

export function getSetupToken(): string | null {
  return sessionStorage.getItem(SETUP_TOKEN_KEY)
}

export function setSetupToken(token: string): void {
  sessionStorage.setItem(SETUP_TOKEN_KEY, token)
}

export function clearSetupToken(): void {
  sessionStorage.removeItem(SETUP_TOKEN_KEY)
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
  clearSetupToken()
}
