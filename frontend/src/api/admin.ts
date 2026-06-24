import type { AppResponse } from "../types/auth"
import type {
  UserAdminResponse,
  UserListResponse,
  UserCreatedResponse,
  RoleResponse,
  RoleListResponse,
} from "../types/admin"
import { api } from "../composables/useApi"

export async function listUsers(
  search?: string,
  page = 1,
  perPage = 20,
): Promise<UserListResponse> {
  const { data } = await api.get("/api/auth/users", {
    params: { search, page, per_page: perPage },
  })
  return data
}

export async function getUser(id: string): Promise<UserAdminResponse> {
  const { data } = await api.get(`/api/auth/users/${id}`)
  return data
}

export async function createUser(body: {
  email: string
  username?: string
  full_name?: string
  role_name?: string
}): Promise<UserCreatedResponse> {
  const { data } = await api.post("/api/auth/register", body)
  return data
}

export async function updateUser(
  id: string,
  body: Partial<{ email: string; username: string; full_name: string; is_active: boolean }>,
): Promise<UserAdminResponse> {
  const { data } = await api.patch(`/api/auth/users/${id}`, body)
  return data
}

export async function deleteUser(id: string): Promise<boolean> {
  const { data } = await api.delete(`/api/auth/users/${id}`)
  return data.deleted
}

export async function resetUserAuth(id: string): Promise<{ message: string }> {
  const { data } = await api.post(`/api/auth/admin/users/${id}/reset-auth`)
  return data
}

export async function resendWelcome(id: string): Promise<{ message: string }> {
  const { data } = await api.post(`/api/auth/admin/users/${id}/resend-welcome`)
  return data
}

export async function getUserRoles(userId: string): Promise<string[]> {
  const { data } = await api.get("/api/auth/roles", { params: { user_id: userId } })
  return data
}

export async function assignRole(userId: string, roleName: string): Promise<boolean> {
  const { data } = await api.post("/api/auth/roles", { role_name: roleName }, { params: { user_id: userId } })
  return data.assigned
}

export async function revokeRole(userId: string, roleName: string): Promise<boolean> {
  const { data } = await api.delete("/api/auth/roles", {
    params: { user_id: userId },
    data: { role_name: roleName },
  })
  return data.revoked
}

export async function listRoles(): Promise<RoleListResponse> {
  const { data } = await api.get("/api/auth/roles/all")
  return data
}

export async function getRole(name: string): Promise<RoleResponse> {
  const { data } = await api.get(`/api/auth/roles/${encodeURIComponent(name)}`)
  return data
}

export async function createRole(name: string, description?: string): Promise<RoleResponse> {
  const { data } = await api.post("/api/auth/roles/create", { name, description })
  return data
}

export async function deleteRole(roleId: string): Promise<boolean> {
  const { data } = await api.delete(`/api/auth/roles/${roleId}`)
  return data.deleted
}

export async function addPermission(
  roleName: string,
  resource: string,
  action: string,
): Promise<boolean> {
  const { data } = await api.post(
    `/api/auth/roles/${encodeURIComponent(roleName)}/permissions`,
    { resource, action },
  )
  return data.added
}

export async function removePermission(
  roleName: string,
  resource: string,
  action: string,
): Promise<boolean> {
  const { data } = await api.delete(
    `/api/auth/roles/${encodeURIComponent(roleName)}/permissions`,
    { data: { resource, action } },
  )
  return data.removed
}

export async function listAllApps(): Promise<AppResponse[]> {
  const { data } = await api.get("/api/auth/admin/apps")
  return data
}

export async function getUserApps(userId: string): Promise<string[]> {
  const { data } = await api.get(`/api/auth/admin/apps/users/${userId}`)
  return data.app_slugs
}

export async function registerUserApp(userId: string, appSlug: string): Promise<boolean> {
  const { data } = await api.post("/api/auth/admin/apps/register", { user_id: userId, app_slug: appSlug })
  return data.registered
}

export async function unregisterUserApp(userId: string, appSlug: string): Promise<boolean> {
  const { data } = await api.post("/api/auth/admin/apps/unregister", { user_id: userId, app_slug: appSlug })
  return data.unregistered
}
