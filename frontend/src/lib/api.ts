import type {
  Document,
  DocumentListResponse,
  DocumentImportRequest,
  RAGQueryRequest,
  RAGQueryResponse,
  IndexStatus,
  IndexBuildRequest,
  LibraryStats,
  DuplicatesResponse,
  SystemHealth,
  Configuration,
  SearchFilters,
  BaseResponse,
} from '../types'

const API_BASE_URL = '/api'

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public statusText: string
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorText = await response.text()
    throw new ApiError(
      `API Error: ${response.status} ${response.statusText} - ${errorText}`,
      response.status,
      response.statusText
    )
  }

  const contentType = response.headers.get('content-type')
  if (contentType && contentType.includes('application/json')) {
    return response.json()
  }

  return response.text() as unknown as T
}

async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`

  const defaultHeaders = {
    'Content-Type': 'application/json',
  }

  const config: RequestInit = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  }

  try {
    const response = await fetch(url, config)
    return handleResponse<T>(response)
  } catch (error) {
    if (error instanceof ApiError) {
      throw error
    }
    throw new Error(`Network error: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }
}

export const api = {
  // Document operations
  async getDocuments(filters?: SearchFilters): Promise<DocumentListResponse> {
    const params = new URLSearchParams()

    if (filters?.query) params.append('query', filters.query)
    if (filters?.show_missing_files !== undefined) {
      params.append('show_missing_files', filters.show_missing_files.toString())
    }
    if (filters?.sort_by) params.append('sort_by', filters.sort_by)
    if (filters?.sort_order) params.append('sort_order', filters.sort_order)
    if (filters?.page) params.append('page', filters.page.toString())
    if (filters?.per_page) params.append('per_page', filters.per_page.toString())

    const queryString = params.toString()
    const endpoint = queryString ? `/documents?${queryString}` : '/documents'

    return apiRequest<DocumentListResponse>(endpoint)
  },

  async getDocument(id: number): Promise<Document> {
    return apiRequest<Document>(`/documents/${id}`)
  },

  async uploadDocument(file: File, options?: DocumentImportRequest): Promise<BaseResponse> {
    const formData = new FormData()
    formData.append('file', file)

    if (options?.title) formData.append('title', options.title)
    if (options?.check_duplicates !== undefined) {
      formData.append('check_duplicates', options.check_duplicates.toString())
    }
    if (options?.auto_build_index !== undefined) {
      formData.append('auto_build_index', options.auto_build_index.toString())
    }

    return apiRequest<BaseResponse>('/documents/upload', {
      method: 'POST',
      headers: {}, // Let browser set Content-Type for FormData
      body: formData,
    })
  },

  async updateDocument(id: number, updates: Partial<Document>): Promise<BaseResponse> {
    return apiRequest<BaseResponse>(`/documents/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    })
  },

  async deleteDocument(id: number): Promise<BaseResponse> {
    return apiRequest<BaseResponse>(`/documents/${id}`, {
      method: 'DELETE',
    })
  },

  // RAG operations
  async queryDocument(request: RAGQueryRequest): Promise<RAGQueryResponse> {
    return apiRequest<RAGQueryResponse>('/rag/query', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  },

  async getIndexStatus(documentId: number): Promise<IndexStatus> {
    return apiRequest<IndexStatus>(`/rag/index/${documentId}/status`)
  },

  async buildIndex(request: IndexBuildRequest): Promise<BaseResponse> {
    return apiRequest<BaseResponse>('/rag/index/build', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  },

  async deleteIndex(documentId: number): Promise<BaseResponse> {
    return apiRequest<BaseResponse>(`/rag/index/${documentId}`, {
      method: 'DELETE',
    })
  },

  // Library management
  async getLibraryStats(): Promise<LibraryStats> {
    return apiRequest<LibraryStats>('/library/stats')
  },

  async findDuplicates(): Promise<DuplicatesResponse> {
    return apiRequest<DuplicatesResponse>('/library/duplicates')
  },

  async cleanupLibrary(): Promise<BaseResponse> {
    return apiRequest<BaseResponse>('/library/cleanup', {
      method: 'POST',
    })
  },

  async rebuildAllIndexes(): Promise<BaseResponse> {
    return apiRequest<BaseResponse>('/library/rebuild-indexes', {
      method: 'POST',
    })
  },

  // System operations
  async getSystemHealth(): Promise<SystemHealth> {
    return apiRequest<SystemHealth>('/system/health')
  },

  async getConfiguration(): Promise<Configuration> {
    return apiRequest<Configuration>('/system/config')
  },

  async initializeSystem(): Promise<BaseResponse> {
    return apiRequest<BaseResponse>('/system/initialize', {
      method: 'POST',
    })
  },

  // File operations
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

  async getDocumentContent(id: number): Promise<string> {
    return apiRequest<string>(`/documents/${id}/content`)
  },
}
