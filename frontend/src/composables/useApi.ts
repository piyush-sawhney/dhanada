import axios from "axios"
import { getAccessToken, getRefreshToken, setAccessToken, setRefreshToken, clearTokens } from "../utils/token"
import { refreshTokens } from "../api/auth"

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "",
  headers: { "Content-Type": "application/json" },
})

let isRefreshing = false
let pendingRequests: Array<(token: string) => void> = []

api.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error)
    }

    const refreshToken = getRefreshToken()
    if (!refreshToken) {
      clearTokens()
      window.location.href = "/login"
      return Promise.reject(error)
    }

    if (isRefreshing) {
      return new Promise((resolve) => {
        pendingRequests.push((token: string) => {
          originalRequest.headers.Authorization = `Bearer ${token}`
          resolve(api(originalRequest))
        })
      })
    }

    originalRequest._retry = true
    isRefreshing = true

    try {
      const response = await refreshTokens(refreshToken)
      setAccessToken(response.access_token)
      setRefreshToken(response.refresh_token)

      pendingRequests.forEach((cb) => cb(response.access_token))
      pendingRequests = []

      originalRequest.headers.Authorization = `Bearer ${response.access_token}`
      return api(originalRequest)
    } catch {
      clearTokens()
      pendingRequests = []
      window.location.href = "/login"
      return Promise.reject(error)
    } finally {
      isRefreshing = false
    }
  },
)
