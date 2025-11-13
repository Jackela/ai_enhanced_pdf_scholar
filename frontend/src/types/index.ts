// Document types
export interface DocumentLinks {
  self: string | null
  related?: Record<string, string> | null
}

export interface Document {
  id: number
  title: string
  file_path: string | null
  file_hash: string
  file_size: number | null
  page_count: number | null
  preview_url?: string | null
  thumbnail_url?: string | null
  created_at: string
  updated_at: string
  last_accessed: string | null
  metadata: Record<string, unknown> | null
  is_file_available: boolean
  content_hash?: string | null
  _links?: DocumentLinks
}

export interface ApiErrorDetail {
  code: string
  message: string
  field?: string
  details?: Record<string, unknown>
}

export interface ApiMeta {
  timestamp: string
  version: string
  request_id?: string | null
}

export interface PaginationMeta extends ApiMeta {
  page: number
  per_page: number
  total: number
  total_pages: number
  has_next: boolean
  has_prev: boolean
}

export interface ApiResponse<T> {
  success: boolean
  data: T | null
  meta: ApiMeta
  errors: ApiErrorDetail[] | null
}

export type PaginatedResponse<T> = ApiResponse<T[]> & {
  meta: PaginationMeta
}

export type DocumentResponse = ApiResponse<Document>

export type DocumentListResponse = PaginatedResponse<Document>

export interface DocumentImportRequest {
  title?: string
  check_duplicates?: boolean
  auto_build_index?: boolean
}

// RAG types
export interface RAGQueryRequest {
  query: string
  document_id: number
  use_cache?: boolean
}

export interface RAGQueryResponse {
  success: boolean
  query: string
  response: string
  document_id: number
  from_cache?: boolean
  processing_time_ms?: number
  message?: string
}

export interface QueryRequest {
  query: string
  include_sources?: boolean
  use_cache?: boolean
  streaming?: boolean
}

export type QueryResponse = ApiResponse<{
  query: string
  response: string
  document_id?: number
  sources?: DocumentSource[]
}>

export interface MultiDocumentQueryRequest extends QueryRequest {
  document_ids: number[]
  max_results?: number
}

export interface IndexStatus {
  success: boolean
  document_id: number
  has_index: boolean
  index_valid: boolean
  index_path: string | null
  chunk_count: number
  created_at: string | null
  can_query: boolean
  message?: string
}

export interface IndexBuildRequest {
  document_id: number
  force_rebuild?: boolean
}

// Library management types
export interface LibraryStats {
  success: boolean
  documents: {
    total_documents: number
    size_stats: {
      total_size_mb: number
      average_size_mb: number
      largest_size_mb: number
    }
  }
  vector_indexes: {
    total_indexes: number
    orphaned_count: number
    invalid_count: number
    coverage: {
      coverage_percentage: number
    }
  }
  cache?: {
    total_entries: number
    hit_rate_percent: number
    total_storage_kb: number
  }
  storage?: {
    total_size_mb: number
    active_indexes: number
    backup_count: number
  }
  health: {
    orphaned_indexes: number
    invalid_indexes: number
    index_coverage: number
  }
}

export interface DuplicateGroup {
  criteria: string
  documents: Document[]
}

export interface DuplicatesResponse {
  success: boolean
  duplicate_groups: DuplicateGroup[]
  total_duplicates: number
  message?: string
}

// System types
export interface SystemHealth {
  success: boolean
  status: 'healthy' | 'degraded' | 'unhealthy'
  database_connected: boolean
  rag_service_available: boolean
  api_key_configured: boolean
  storage_health: string
  uptime_seconds?: number
  message?: string
}

export interface Configuration {
  success: boolean
  features: {
    document_upload: boolean
    rag_queries: boolean
    vector_indexing: boolean
    cache_system: boolean
    websocket_support: boolean
    duplicate_detection: boolean
    library_management: boolean
  }
  limits: {
    max_file_size_mb: number
    max_query_length: number
    allowed_file_types: string[]
    max_documents: number
    max_concurrent_queries: number
  }
  version: string
  message?: string
}

// WebSocket message types
export interface WebSocketMessage {
  type: string
  data?: unknown
}

export interface RAGProgressMessage extends WebSocketMessage {
  type: 'rag_progress'
  message: string
  document_id?: number
}

export interface RAGResponseMessage extends WebSocketMessage {
  type: 'rag_response'
  query: string
  response: string
  document_id: number
  processing_time_ms?: number
}

export interface IndexProgressMessage extends WebSocketMessage {
  type: 'index_progress'
  document_id: number
  document_title: string
  status: string
  progress_percentage?: number
}

export interface ErrorMessage extends WebSocketMessage {
  type: 'error'
  error: string
  error_code?: string
}

export interface DocumentUpdateMessage extends WebSocketMessage {
  type: 'document_update'
  document_id: number
  action: 'created' | 'updated' | 'deleted'
  data?: Record<string, unknown>
}

// UI state types
export interface UIState {
  sidebarOpen: boolean
  currentView: 'library' | 'viewer' | 'chat'
  selectedDocument: Document | null
  isLoading: boolean
  error: string | null
}

// Search and filter types
export interface SearchFilters {
  query?: string
  show_missing_files?: boolean
  sort_by?: 'created_at' | 'updated_at' | 'last_accessed' | 'title' | 'file_size'
  sort_order?: 'asc' | 'desc'
  page?: number
  per_page?: number
}

// API response wrapper
export interface BaseResponse {
  success: boolean
  message?: string
  data?: unknown
}

export interface ErrorResponse extends BaseResponse {
  success: false
  error_code?: string
  details?: Record<string, unknown>
}

// Chat types
export interface ChatMessage {
  id: string
  type: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  document_id?: number
  from_cache?: boolean
}

export interface ChatSession {
  id: string
  document_id?: number
  document_title?: string
  messages: ChatMessage[]
  created_at: string
  updated_at: string
}

// Upload types
export interface UploadProgress {
  file_name: string
  progress: number
  status: 'uploading' | 'processing' | 'completed' | 'error'
  error?: string
}

// Theme types
export type Theme = 'light' | 'dark' | 'system'

// PDF viewer types
export interface PDFViewerState {
  currentPage: number
  totalPages: number
  scale: number
  isLoading: boolean
  error: string | null
}

// Multi-Document Collection types
export interface DocumentCollection {
  id: number
  name: string
  description: string | null
  document_ids: number[]
  document_count: number
  created_at: string | null
  updated_at: string | null
}

export interface CreateCollectionRequest {
  name: string
  description?: string
  document_ids: number[]
}

export interface UpdateCollectionRequest {
  name?: string
  description?: string
}

export interface CollectionListResponse {
  collections: DocumentCollection[]
  total_count: number
  page: number
  limit: number
}

export interface DocumentSource {
  document_id: number
  relevance_score: number
  excerpt: string
  page_number?: number
  chunk_id?: string
}

export interface CrossReference {
  source_doc_id: number
  target_doc_id: number
  relation_type: string
  confidence: number
  description?: string
}

export interface CrossDocumentQueryRequest {
  query: string
  max_results?: number
  user_id?: string
}

export interface MultiDocumentQueryResponse {
  id: number
  query: string
  answer: string
  confidence: number
  sources: DocumentSource[]
  cross_references: CrossReference[]
  processing_time_ms: number
  tokens_used?: number
  status: string
  created_at: string
}

export interface QueryHistoryResponse {
  queries: MultiDocumentQueryResponse[]
  total_count: number
  page: number
  limit: number
}

export interface CollectionStatistics {
  collection_id: number
  name: string
  document_count: number
  total_file_size: number
  avg_file_size: number
  created_at: string | null
  recent_queries: number
  avg_query_time_ms?: number
}
