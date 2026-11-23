const API_BASE = '/api/v1'

export type Account = {
  id: string
  email: string
  is_central_admin: boolean
}

export type Direction = {
  id: string
  name: string
  created_at: string
}

export type Service = {
  id: string
  direction_id: string
  direction_name: string
  name: string
  created_at: string
}

export type Category = {
  id: string
  parent_id: string | null
  parent_name: string | null
  name: string
  created_at: string
  retention_years: number | null
}

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

function cookieValue(name: string) {
  const prefix = `${name}=`
  const cookie = document.cookie.split('; ').find((part) => part.startsWith(prefix))
  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : undefined
}

function csrfToken() {
  return cookieValue('__Host-maa_csrf') ?? cookieValue('maa_csrf')
}

async function request<T>(path: string, init: RequestInit = {}, csrfProtected = true): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase()
  const headers = new Headers(init.headers)
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (csrfProtected && !['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const token = csrfToken()
    if (!token) throw new ApiError(403, 'Le jeton de protection de session est absent. Reconnectez-vous.')
    headers.set('X-CSRF-Token', token)
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    method,
    headers,
    credentials: 'same-origin',
    cache: 'no-store',
  })

  if (!response.ok) {
    let message = `La requête a échoué (${response.status}).`
    try {
      const problem = await response.json() as { detail?: string; title?: string }
      if (response.status === 401) message = 'Votre session a expiré. Reconnectez-vous.'
      else if (problem.detail) message = problem.detail
      else if (problem.title) message = problem.title
    } catch {
      // Keep the safe, status-based message when the response is not JSON.
    }
    throw new ApiError(response.status, message)
  }
  if (response.status === 204) return undefined as T
  return await response.json() as T
}

export function getCurrentAccount() {
  return request<Account>('/auth/me')
}

export function login(email: string, password: string) {
  return request<Account>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  }, false)
}

export function logout() {
  return request<void>('/auth/logout', { method: 'POST' })
}

export function listDirections() {
  return request<Direction[]>('/admin/catalog/directions')
}

export function createDirection(name: string) {
  return request<Direction>('/admin/catalog/directions', {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
}

export function renameDirection(directionId: string, name: string) {
  return request<Direction>(`/admin/catalog/directions/${encodeURIComponent(directionId)}`, {
    method: 'PATCH',
    body: JSON.stringify({ name }),
  })
}

export function listServices(directionId?: string) {
  const query = directionId ? `?direction_id=${encodeURIComponent(directionId)}` : ''
  return request<Service[]>(`/admin/catalog/services${query}`)
}

export function createService(directionId: string, name: string) {
  return request<Service>('/admin/catalog/services', {
    method: 'POST',
    body: JSON.stringify({ direction_id: directionId, name }),
  })
}

export function renameService(serviceId: string, name: string) {
  return request<Service>(`/admin/catalog/services/${encodeURIComponent(serviceId)}`, {
    method: 'PATCH',
    body: JSON.stringify({ name }),
  })
}

export type CategoryQuery = {
  rootsOnly?: boolean
  parentId?: string
}

export function listCategories(options: CategoryQuery = {}) {
  const params = new URLSearchParams()
  if (options.rootsOnly) params.set('roots_only', 'true')
  if (options.parentId) params.set('parent_id', options.parentId)
  const query = params.toString()
  return request<Category[]>(`/admin/catalog/categories${query ? `?${query}` : ''}`)
}

export function createCategory(parentId: string | null, name: string, retentionYears?: number | null) {
  return request<Category>('/admin/catalog/categories', {
    method: 'POST',
    body: JSON.stringify({ parent_id: parentId, name, retention_years: retentionYears ?? null }),
  })
}

export function updateCategory(categoryId: string, name?: string | null, retentionYears?: number | null, updateRetention = false) {
  const body: Record<string, unknown> = {}
  if (name !== undefined && name !== null) body.name = name
  if (updateRetention) body.retention_years = retentionYears ?? null
  return request<Category>(`/admin/catalog/categories/${encodeURIComponent(categoryId)}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

export function renameCategory(categoryId: string, name: string) {
  return updateCategory(categoryId, name)
}
