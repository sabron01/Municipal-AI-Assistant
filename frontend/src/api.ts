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

export type DocumentSummary = {
  id: string
  title: string
  service_id: string
  category_id: string
  current_version_id: string
  status: string
  created_at: string
  updated_at: string
  description: string | null
  reference_number: string | null
  document_date: string
  issuer: string | null
  keywords: string[]
  confidentiality_level: string | null
  retention_code: string | null
  aggregate_version: number
}

export type DocumentVersion = {
  id: string
  sequence: number
  original_filename: string
  detected_mime_type: string
  size_bytes: number
  sha256: string
  created_at: string
}

export type DocumentPage = {
  items: DocumentSummary[]
  next_cursor: string | null
}

export type DocumentCreateInput = {
  title: string
  serviceId: string
  categoryId: string
  documentDate: string
  referenceNumber: string
  description?: string | null
  issuer?: string | null
  keywords?: string[]
  confidentialityLevel?: string | null
  retentionCode?: string | null
  file: File
}

export function listDocuments(options: { serviceId?: string; categoryId?: string; cursor?: string; limit?: number } = {}) {
  const params = new URLSearchParams()
  if (options.serviceId) params.set('service_id', options.serviceId)
  if (options.categoryId) params.set('category_id', options.categoryId)
  if (options.cursor) params.set('cursor', options.cursor)
  if (options.limit) params.set('limit', String(options.limit))
  const query = params.toString()
  return request<DocumentPage>(`/documents${query ? `?${query}` : ''}`)
}

export function getDocument(documentId: string) {
  return request<DocumentSummary>(`/documents/${encodeURIComponent(documentId)}`)
}

export async function createDocument(input: DocumentCreateInput) {
  const form = new FormData()
  form.set('title', input.title)
  form.set('service_id', input.serviceId)
  form.set('category_id', input.categoryId)
  form.set('document_date', input.documentDate)
  form.set('reference_number', input.referenceNumber)
  if (input.description) form.set('description', input.description)
  if (input.issuer) form.set('issuer', input.issuer)
  for (const keyword of input.keywords ?? []) form.append('keywords', keyword)
  if (input.confidentialityLevel) form.set('confidentiality_level', input.confidentialityLevel)
  if (input.retentionCode) form.set('retention_code', input.retentionCode)
  form.set('file', input.file)
  return request<DocumentSummary>('/documents', { method: 'POST', body: form })
}

export function updateDocument(documentId: string, payload: {
  title: string
  serviceId: string
  categoryId: string
  documentDate: string
  referenceNumber: string
  description?: string | null
  issuer?: string | null
  keywords?: string[]
  confidentialityLevel?: string | null
  retentionCode?: string | null
}, ifMatch: string) {
  return request<DocumentSummary>(`/documents/${encodeURIComponent(documentId)}`, {
    method: 'PATCH',
    body: JSON.stringify({
      title: payload.title,
      service_id: payload.serviceId,
      category_id: payload.categoryId,
      document_date: payload.documentDate,
      reference_number: payload.referenceNumber,
      description: payload.description ?? null,
      issuer: payload.issuer ?? null,
      keywords: payload.keywords ?? [],
      confidentiality_level: payload.confidentialityLevel ?? null,
      retention_code: payload.retentionCode ?? null,
    }),
    headers: { 'If-Match': ifMatch },
  })
}

export function addDocumentVersion(documentId: string, file: File, ifMatch: string) {
  const form = new FormData()
  form.set('file', file)
  return request<DocumentSummary>(`/documents/${encodeURIComponent(documentId)}/versions`, {
    method: 'POST',
    body: form,
    headers: { 'If-Match': ifMatch },
  })
}

export function listDocumentVersions(documentId: string) {
  return request<DocumentVersion[]>(`/documents/${encodeURIComponent(documentId)}/versions`)
}

export function softDeleteDocument(documentId: string, ifMatch: string) {
  return request<void>(`/documents/${encodeURIComponent(documentId)}`, {
    method: 'DELETE',
    headers: { 'If-Match': ifMatch },
  })
}

export function restoreDocument(documentId: string, ifMatch: string) {
  return request<DocumentSummary>(`/documents/${encodeURIComponent(documentId)}/restore`, {
    method: 'POST',
    headers: { 'If-Match': ifMatch },
  })
}

export function purgeDocument(documentId: string, ifMatch: string) {
  return request<void>(`/documents/${encodeURIComponent(documentId)}/purge`, {
    method: 'DELETE',
    headers: { 'If-Match': ifMatch },
  })
}
