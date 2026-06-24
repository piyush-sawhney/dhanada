export interface LoginRequest {
  email: string
  password: string
  totp_token?: string | null
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface SetupRequiredResponse {
  status: "setup_required"
  setup_token: string
  expires_in: number
}

export interface BootstrapRequest {
  email: string
  password: string
  full_name?: string | null
}

export interface BootstrapStatusResponse {
  needs_bootstrap: boolean
}

export interface BootstrapCompleteResponse extends TokenResponse {
  user: UserResponse
  totp_required: boolean
}

export interface SetupCompleteRequest {
  new_password?: string
}

export interface TOTPEnableResponse {
  secret: string
  provisioning_uri: string
  backup_codes: string[] | null
}

export interface TOTPVerifyRequest {
  token: string
}

export interface UserResponse {
  id: string
  email: string
  username: string
  full_name: string | null
  is_active: boolean
  is_superuser: boolean
  email_verified: boolean
  roles: string[]
  created_at: string
  updated_at: string
}

export interface ErrorResponse {
  detail: string
  hint?: string | null
}

export type LoginResponse = TokenResponse | SetupRequiredResponse
