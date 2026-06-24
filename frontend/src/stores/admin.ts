import { defineStore } from "pinia"
import { ref, shallowRef } from "vue"
import type { AppResponse } from "../types/auth"
import type { UserAdminResponse, RoleResponse } from "../types/admin"
import * as adminApi from "../api/admin"

export const useAdminStore = defineStore("admin", () => {
  const users = ref<UserAdminResponse[]>([])
  const total = shallowRef(0)
  const page = shallowRef(1)
  const perPage = shallowRef(20)
  const search = shallowRef("")
  const loading = shallowRef(false)

  const roles = ref<RoleResponse[]>([])
  const allApps = ref<AppResponse[]>([])

  async function fetchUsers() {
    loading.value = true
    try {
      const res = await adminApi.listUsers(search.value || undefined, page.value, perPage.value)
      users.value = res.users
      total.value = res.total
    } finally {
      loading.value = false
    }
  }

  async function fetchRoles() {
    const res = await adminApi.listRoles()
    roles.value = res.roles
  }

  async function fetchAllApps() {
    allApps.value = await adminApi.listAllApps()
  }

  function setPage(p: number) {
    page.value = p
    fetchUsers()
  }

  function setSearch(q: string) {
    search.value = q
    page.value = 1
    fetchUsers()
  }

  return {
    users, total, page, perPage, search, loading,
    roles, allApps,
    fetchUsers, fetchRoles, fetchAllApps, setPage, setSearch,
  }
})
