import type {
  Document,
  DocumentListResponse,
  DocumentResponse,
  DocumentImportRequest,
  SearchFilters,
  QueryRequest,
  QueryResponse,
  MultiDocumentQueryRequest,
  ApiResponse,
} from '../types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL
  ? `${import.meta.env.VITE_API_BASE_URL}/api`
  : '/api'

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public statusText: string,
    public body?: string
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorText = await response.text()
    throw new ApiError(
      `API Error: ${response.status} ${response.statusText}`,
      response.status,
      response.statusText,
      errorText
    )
  }

  if (response.status === 204 || response.status === 205) {
    return undefined as T
  }

  const contentType = response.headers.get('content-type')
  if (contentType && contentType.includes('application/json')) {
    return response.json() as Promise<T>
  }

  return (response.text() as unknown) as T
}

async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`

  const headers = new Headers(options.headers ?? {})
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const config: RequestInit = {
    ...options,
    headers,
  }

  const response = await fetch(url, config)
  return handleResponse<T>(response)
}

function ensureData<T>(response: ApiResponse<T>): T {
  if (response.data === null || response.data === undefined) {
    throw new ApiError('API response did not include data', 500, 'Missing data')
  }
  return response.data as T
}

export const api = {
  async getDocuments(filters?: SearchFilters): Promise<DocumentListResponse> {
    const params = new URLSearchParams()

    if (filters?.query) params.append('query', filters.query)
    if (filters?.sort_by) params.append('sort_by', filters.sort_by)
    if (filters?.sort_order) params.append('sort_order', filters.sort_order)
    if (filters?.page) params.append('page', filters.page.toString())
    if (filters?.per_page) params.append('per_page', filters.per_page.toString())

    const queryString = params.toString()
    const endpoint = queryString ? `/documents?${queryString}` : '/documents'

    return apiRequest<DocumentListResponse>(endpoint)
  },

  async getDocument(id: number): Promise<Document> {
    const response = await apiRequest<DocumentResponse>(`/documents/${id}`)
    return ensureData<Document>(response)
  },

  async uploadDocument(file: File, options?: DocumentImportRequest): Promise<Document> {
    const formData = new FormData()
    formData.append('file', file)

    const params = new URLSearchParams()
    if (options?.title) params.append('title', options.title)
    if (options?.check_duplicates !== undefined) {
      params.append('check_duplicates', String(options.check_duplicates))
    }
    if (options?.overwrite_duplicates !== undefined) {
      params.append('overwrite_duplicates', String(options.overwrite_duplicates))
    }

    const endpointParams = params.toString()
    const endpoint = endpointParams ? `/documents?${endpointParams}` : '/documents'
    const response = await apiRequest<DocumentResponse>(endpoint, {
      method: 'POST',
      body: formData,
    })

    return ensureData<Document>(response)
  },

  async deleteDocument(id: number): Promise<void> {
    await apiRequest<void>(`/documents/${id}`, {
      method: 'DELETE',
    })
  },

  async downloadDocument(id: number): Promise<Blob> {
    const response = await fetch(`${API_BASE_URL}/documents/${id}/download`)
    if (!response.ok) {
      throw new ApiError(
        `Failed to download document: ${response.statusText}`,
        response.status,
        response.statusText
      )
    }
    return response.blob()
  },

  async queryDocument(documentId: number, payload: QueryRequest): Promise<QueryResponse> {
    return apiRequest<QueryResponse>(`/queries/document/${documentId}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  async queryAcrossDocuments(payload: MultiDocumentQueryRequest): Promise<QueryResponse> {
    return apiRequest<QueryResponse>('/queries/multi-document', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
}
