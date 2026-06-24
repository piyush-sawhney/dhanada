export interface UserAdminResponse {
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

export interface UserListResponse {
  users: UserAdminResponse[]
  total: number
  page: number
  per_page: number
}

export interface UserCreatedResponse {
  id: string
  email: string
  username: string
  full_name: string | null
  is_active: boolean
  is_superuser: boolean
  roles: string[]
  created_at: string
  updated_at: string
}

export interface RolePermissionResponse {
  resource: string
  action: string
}

export interface RoleResponse {
  id: string
  name: string
  description: string | null
  is_system: boolean
  permissions: RolePermissionResponse[]
  created_at: string
  updated_at: string
}

export interface RoleListResponse {
  roles: RoleResponse[]
}
