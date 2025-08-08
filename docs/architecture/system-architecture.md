# System Architecture - AI Enhanced PDF Scholar

## Table of Contents

1. [Overview](#overview)
2. [Architecture Principles](#architecture-principles)
3. [System Components](#system-components)
4. [Data Architecture](#data-architecture)
5. [API Architecture](#api-architecture)
6. [Service Layer Architecture](#service-layer-architecture)
7. [Frontend Architecture](#frontend-architecture)
8. [Security Architecture](#security-architecture)
9. [Deployment Architecture](#deployment-architecture)
10. [Performance & Scalability](#performance--scalability)
11. [Monitoring & Observability](#monitoring--observability)
12. [Future Architecture](#future-architecture)

## Overview

AI Enhanced PDF Scholar is built on a modern, scalable architecture that follows microservices principles while maintaining simplicity for single-user deployments. The system is designed to handle document management, AI-powered analysis, and citation extraction with high performance and reliability.

### High-Level Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        WEB[Web Browser]
        API_CLIENT[API Clients]
        MOBILE[Mobile Apps]
    end
    
    subgraph "API Gateway Layer"
        NGINX[Nginx Reverse Proxy]
        CORS[CORS Handler]
        RATE[Rate Limiting]
    end
    
    subgraph "Application Layer"
        FASTAPI[FastAPI Application]
        WS[WebSocket Manager]
        AUTH[Authentication]
        MIDDLEWARE[Security Middleware]
    end
    
    subgraph "Service Layer"
        DOC_SVC[Document Service]
        RAG_SVC[RAG Service]
        CITE_SVC[Citation Service]
        SEARCH_SVC[Search Service]
        CACHE_SVC[Cache Service]
    end
    
    subgraph "Data Layer"
        SQLITE[(SQLite Database)]
        VECTOR[(Vector Store)]
        FILES[(File Storage)]
        CACHE[(Redis Cache)]
    end
    
    subgraph "External Services"
        GEMINI[Google Gemini AI]
        EMBEDDING[Embedding APIs]
        DOI[DOI Resolution]
    end
    
    WEB --> NGINX
    API_CLIENT --> NGINX
    MOBILE --> NGINX
    
    NGINX --> FASTAPI
    CORS --> FASTAPI
    RATE --> FASTAPI
    
    FASTAPI --> DOC_SVC
    FASTAPI --> RAG_SVC
    FASTAPI --> CITE_SVC
    FASTAPI --> SEARCH_SVC
    WS --> CACHE_SVC
    
    DOC_SVC --> SQLITE
    DOC_SVC --> FILES
    RAG_SVC --> VECTOR
    RAG_SVC --> GEMINI
    CITE_SVC --> SQLITE
    SEARCH_SVC --> CACHE
    CACHE_SVC --> CACHE
    
    RAG_SVC --> EMBEDDING
    CITE_SVC --> DOI
```

### Architecture Characteristics

- **Modular**: Clear separation of concerns with well-defined interfaces
- **Scalable**: Designed to handle growing document collections and user load
- **Resilient**: Graceful degradation and error recovery mechanisms
- **Maintainable**: Clean code architecture following SOLID principles
- **Testable**: Comprehensive test coverage with isolated components
- **Secure**: Multiple layers of security controls and validation

## Architecture Principles

### 1. Domain-Driven Design (DDD)

The system is organized around core business domains:

```mermaid
graph TD
    subgraph "Document Domain"
        DOC_ENTITY[Document Entity]
        DOC_REPO[Document Repository]
        DOC_SERVICE[Document Service]
    end
    
    subgraph "RAG Domain"
        RAG_ENTITY[Index Entity]
        RAG_REPO[Vector Repository]
        RAG_SERVICE[RAG Service]
    end
    
    subgraph "Citation Domain"
        CITE_ENTITY[Citation Entity]
        CITE_REPO[Citation Repository]
        CITE_SERVICE[Citation Service]
    end
    
    subgraph "Library Domain"
        LIB_ENTITY[Library Entity]
        LIB_REPO[Library Repository]
        LIB_SERVICE[Library Service]
    end
```

### 2. Clean Architecture (Hexagonal)

```mermaid
graph TD
    subgraph "External Adapters"
        WEB_UI[Web UI]
        REST_API[REST API]
        CLI[CLI Interface]
    end
    
    subgraph "Application Layer"
        USE_CASES[Use Cases]
        APP_SERVICES[Application Services]
    end
    
    subgraph "Domain Layer"
        ENTITIES[Domain Entities]
        BUSINESS_RULES[Business Rules]
        DOMAIN_SERVICES[Domain Services]
    end
    
    subgraph "Infrastructure Layer"
        DATABASE[Database]
        FILE_SYSTEM[File System]
        EXTERNAL_APIS[External APIs]
    end
    
    WEB_UI --> USE_CASES
    REST_API --> USE_CASES
    CLI --> USE_CASES
    
    USE_CASES --> ENTITIES
    APP_SERVICES --> ENTITIES
    
    ENTITIES --> BUSINESS_RULES
    ENTITIES --> DOMAIN_SERVICES
    
    USE_CASES --> DATABASE
    USE_CASES --> FILE_SYSTEM
    USE_CASES --> EXTERNAL_APIS
```

### 3. SOLID Principles Implementation

#### Single Responsibility Principle (SRP)
```python
# Each class has a single, well-defined responsibility
class DocumentRepository:
    """Responsible only for document data persistence"""
    
class DocumentService:
    """Responsible only for document business logic"""
    
class RAGService:
    """Responsible only for RAG operations"""
```

#### Open/Closed Principle (OCP)
```python
# Open for extension, closed for modification
class BaseEmbeddingProvider(ABC):
    @abstractmethod
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        pass

class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        # OpenAI implementation
        pass

class HuggingFaceEmbeddingProvider(BaseEmbeddingProvider):
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        # HuggingFace implementation
        pass
```

#### Liskov Substitution Principle (LSP)
```python
# Subclasses can replace base classes without breaking functionality
def process_with_embedding_provider(provider: BaseEmbeddingProvider, texts: List[str]):
    embeddings = provider.generate_embeddings(texts)
    return embeddings

# Works with any concrete implementation
openai_provider = OpenAIEmbeddingProvider()
huggingface_provider = HuggingFaceEmbeddingProvider()

process_with_embedding_provider(openai_provider, texts)
process_with_embedding_provider(huggingface_provider, texts)
```

#### Interface Segregation Principle (ISP)
```python
# Clients depend only on methods they use
class IDocumentReader(ABC):
    @abstractmethod
    def read_document(self, document_id: int) -> Document:
        pass

class IDocumentWriter(ABC):
    @abstractmethod
    def create_document(self, document: Document) -> Document:
        pass
    
    @abstractmethod
    def update_document(self, document: Document) -> Document:
        pass

class IDocumentDeleter(ABC):
    @abstractmethod
    def delete_document(self, document_id: int) -> bool:
        pass
```

#### Dependency Inversion Principle (DIP)
```python
# High-level modules don't depend on low-level modules
class DocumentService:
    def __init__(
        self,
        document_repo: IDocumentRepository,
        file_service: IFileService,
        cache_service: ICacheService
    ):
        self.document_repo = document_repo
        self.file_service = file_service
        self.cache_service = cache_service
```

## System Components

### 1. Web Application Layer

```mermaid
graph LR
    subgraph "FastAPI Application"
        MAIN[main.py]
        ROUTES[Route Handlers]
        MIDDLEWARE[Middleware Stack]
        DEPS[Dependencies]
    end
    
    subgraph "Middleware Stack"
        SECURITY[Security Headers]
        CORS[CORS Middleware]
        RATE_LIMIT[Rate Limiting]
        ERROR[Error Handling]
        LOGGING[Request Logging]
    end
    
    MAIN --> ROUTES
    MAIN --> MIDDLEWARE
    ROUTES --> DEPS
    
    MIDDLEWARE --> SECURITY
    MIDDLEWARE --> CORS
    MIDDLEWARE --> RATE_LIMIT
    MIDDLEWARE --> ERROR
    MIDDLEWARE --> LOGGING
```

#### Key Components:

**Main Application (`backend/api/main.py`)**
- FastAPI application factory
- Route registration
- Middleware configuration
- Startup/shutdown event handlers

**Route Handlers (`backend/api/routes/`)**
- RESTful API endpoints
- Request validation using Pydantic
- Response serialization
- Error handling

**Middleware (`backend/api/middleware/`)**
- Security headers injection
- CORS configuration
- Rate limiting enforcement
- Request/response logging

### 2. Service Layer Architecture

```mermaid
graph TD
    subgraph "Service Layer"
        DOC_SVC[Document Service]
        RAG_SVC[RAG Service]
        CITE_SVC[Citation Service]
        LIB_SVC[Library Service]
        CACHE_SVC[Cache Service]
    end
    
    subgraph "Core Services"
        HASH_SVC[Content Hash Service]
        FILE_SVC[File Management Service]
        SEARCH_SVC[Search Service]
        VALIDATION_SVC[Validation Service]
    end
    
    subgraph "External Integration"
        AI_SVC[AI Service Gateway]
        DOI_SVC[DOI Resolution Service]
        EMBED_SVC[Embedding Service]
    end
    
    DOC_SVC --> HASH_SVC
    DOC_SVC --> FILE_SVC
    DOC_SVC --> VALIDATION_SVC
    
    RAG_SVC --> AI_SVC
    RAG_SVC --> EMBED_SVC
    RAG_SVC --> CACHE_SVC
    
    CITE_SVC --> DOI_SVC
    CITE_SVC --> VALIDATION_SVC
    
    LIB_SVC --> SEARCH_SVC
    LIB_SVC --> CACHE_SVC
```

#### Service Characteristics:

**Business Logic Encapsulation**
```python
class DocumentService:
    """Encapsulates all document-related business logic"""
    
    def __init__(self, repository: IDocumentRepository, file_service: IFileService):
        self.repository = repository
        self.file_service = file_service
    
    async def create_document(self, file_data: bytes, metadata: DocumentMetadata) -> Document:
        # 1. Validate file format
        # 2. Generate content hash
        # 3. Check for duplicates
        # 4. Store file securely
        # 5. Create database record
        # 6. Generate events
        pass
```

**Interface-Driven Design**
```python
class IRAGService(ABC):
    @abstractmethod
    async def build_index(self, document_id: int, options: IndexOptions) -> IndexResult:
        pass
    
    @abstractmethod
    async def query(self, query: str, document_id: int, options: QueryOptions) -> RAGResponse:
        pass
    
    @abstractmethod
    async def get_index_status(self, document_id: int) -> IndexStatus:
        pass
```

### 3. Repository Layer

```mermaid
graph TD
    subgraph "Repository Interfaces"
        I_DOC_REPO[IDocumentRepository]
        I_CITE_REPO[ICitationRepository]
        I_VECTOR_REPO[IVectorRepository]
        I_USER_REPO[IUserRepository]
    end
    
    subgraph "Concrete Repositories"
        DOC_REPO[SQLiteDocumentRepository]
        CITE_REPO[SQLiteCitationRepository]
        VECTOR_REPO[ChromaVectorRepository]
        USER_REPO[SQLiteUserRepository]
    end
    
    subgraph "Base Infrastructure"
        BASE_REPO[BaseRepository]
        DB_CONNECTION[Database Connection]
        TRANSACTION_MGR[Transaction Manager]
    end
    
    I_DOC_REPO --> DOC_REPO
    I_CITE_REPO --> CITE_REPO
    I_VECTOR_REPO --> VECTOR_REPO
    I_USER_REPO --> USER_REPO
    
    DOC_REPO --> BASE_REPO
    CITE_REPO --> BASE_REPO
    VECTOR_REPO --> BASE_REPO
    USER_REPO --> BASE_REPO
    
    BASE_REPO --> DB_CONNECTION
    BASE_REPO --> TRANSACTION_MGR
```

#### Repository Pattern Implementation:

```python
class BaseRepository(ABC, Generic[T]):
    """Base repository with common CRUD operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    @abstractmethod
    def get_model_class(self) -> Type[T]:
        pass
    
    async def get_by_id(self, entity_id: int) -> Optional[T]:
        result = await self.db.execute(
            select(self.get_model_class()).where(self.get_model_class().id == entity_id)
        )
        return result.scalar_one_or_none()
    
    async def create(self, entity: T) -> T:
        self.db.add(entity)
        await self.db.commit()
        await self.db.refresh(entity)
        return entity
    
    async def update(self, entity: T) -> T:
        await self.db.commit()
        await self.db.refresh(entity)
        return entity
    
    async def delete(self, entity_id: int) -> bool:
        entity = await self.get_by_id(entity_id)
        if entity:
            await self.db.delete(entity)
            await self.db.commit()
            return True
        return False
```

## Data Architecture

### 1. Database Schema

```mermaid
erDiagram
    DOCUMENTS {
        int id PK
        string title
        string file_path
        string file_hash
        string content_hash
        int file_size
        int page_count
        datetime created_at
        datetime updated_at
        datetime last_accessed
        json metadata
        boolean is_file_available
    }
    
    CITATIONS {
        int id PK
        int document_id FK
        string raw_text
        string authors
        string title
        string journal_or_venue
        int publication_year
        string doi
        string page_range
        string citation_type
        float confidence_score
        datetime created_at
        datetime updated_at
    }
    
    CITATION_RELATIONS {
        int id PK
        int source_document_id FK
        int source_citation_id FK
        int target_document_id FK
        string relation_type
        float confidence_score
        datetime created_at
    }
    
    VECTOR_INDEXES {
        int id PK
        int document_id FK
        string chunk_id
        text content
        json metadata
        vector embedding
        datetime created_at
    }
    
    USERS {
        int id PK
        string username
        string email
        string password_hash
        json preferences
        datetime created_at
        datetime last_login
    }
    
    DOCUMENTS ||--o{ CITATIONS : "contains"
    DOCUMENTS ||--o{ VECTOR_INDEXES : "indexed_by"
    DOCUMENTS ||--o{ CITATION_RELATIONS : "source"
    DOCUMENTS ||--o{ CITATION_RELATIONS : "target"
    CITATIONS ||--o{ CITATION_RELATIONS : "references"
    USERS ||--o{ DOCUMENTS : "owns"
```

### 2. Data Flow Architecture

```mermaid
graph TD
    subgraph "Data Ingestion"
        UPLOAD[File Upload]
        VALIDATION[Format Validation]
        CONTENT_EXTRACT[Content Extraction]
        HASH_GEN[Hash Generation]
    end
    
    subgraph "Processing Pipeline"
        DUPLICATE_CHECK[Duplicate Detection]
        METADATA_EXTRACT[Metadata Extraction]
        TEXT_PROCESS[Text Processing]
        CHUNK_GEN[Chunk Generation]
    end
    
    subgraph "AI Processing"
        EMBEDDING_GEN[Embedding Generation]
        VECTOR_INDEX[Vector Indexing]
        CITATION_EXTRACT[Citation Extraction]
        CITATION_PARSE[Citation Parsing]
    end
    
    subgraph "Storage"
        FILE_STORE[(File Storage)]
        DATABASE[(Database)]
        VECTOR_STORE[(Vector Store)]
        CACHE[(Cache)]
    end
    
    UPLOAD --> VALIDATION
    VALIDATION --> CONTENT_EXTRACT
    CONTENT_EXTRACT --> HASH_GEN
    
    HASH_GEN --> DUPLICATE_CHECK
    DUPLICATE_CHECK --> METADATA_EXTRACT
    METADATA_EXTRACT --> TEXT_PROCESS
    TEXT_PROCESS --> CHUNK_GEN
    
    CHUNK_GEN --> EMBEDDING_GEN
    EMBEDDING_GEN --> VECTOR_INDEX
    TEXT_PROCESS --> CITATION_EXTRACT
    CITATION_EXTRACT --> CITATION_PARSE
    
    CONTENT_EXTRACT --> FILE_STORE
    METADATA_EXTRACT --> DATABASE
    VECTOR_INDEX --> VECTOR_STORE
    CITATION_PARSE --> DATABASE
    
    DATABASE --> CACHE
    VECTOR_STORE --> CACHE
```

### 3. Caching Strategy

```mermaid
graph LR
    subgraph "Cache Layers"
        L1[L1: Application Cache]
        L2[L2: Redis Cache]
        L3[L3: Database]
        L4[L4: File System]
    end
    
    subgraph "Cache Types"
        QUERY[Query Results]
        EMBEDDING[Embeddings]
        CONTENT[Document Content]
        METADATA[Metadata]
        SESSION[Session Data]
    end
    
    APPLICATION --> L1
    L1 --> L2
    L2 --> L3
    L3 --> L4
    
    QUERY --> L1
    EMBEDDING --> L2
    CONTENT --> L2
    METADATA --> L1
    SESSION --> L2
```

## API Architecture

### 1. RESTful API Design

```mermaid
graph TD
    subgraph "API Gateway"
        NGINX[Nginx Reverse Proxy]
        RATE_LIMITER[Rate Limiter]
        LOAD_BALANCER[Load Balancer]
    end
    
    subgraph "API Layer"
        FASTAPI[FastAPI App]
        AUTH_MIDDLEWARE[Auth Middleware]
        VALIDATION[Request Validation]
        SERIALIZATION[Response Serialization]
    end
    
    subgraph "Route Groups"
        SYSTEM_ROUTES[/api/system/*]
        DOC_ROUTES[/api/documents/*]
        RAG_ROUTES[/api/rag/*]
        CITE_ROUTES[/api/citations/*]
        LIB_ROUTES[/api/library/*]
    end
    
    CLIENT --> NGINX
    NGINX --> RATE_LIMITER
    RATE_LIMITER --> LOAD_BALANCER
    LOAD_BALANCER --> FASTAPI
    
    FASTAPI --> AUTH_MIDDLEWARE
    AUTH_MIDDLEWARE --> VALIDATION
    VALIDATION --> SERIALIZATION
    
    SERIALIZATION --> SYSTEM_ROUTES
    SERIALIZATION --> DOC_ROUTES
    SERIALIZATION --> RAG_ROUTES
    SERIALIZATION --> CITE_ROUTES
    SERIALIZATION --> LIB_ROUTES
```

#### API Design Principles:

**1. Resource-Based URLs**
```
GET /api/documents/                    # List documents
GET /api/documents/{id}                # Get specific document
POST /api/documents/upload             # Create new document
PUT /api/documents/{id}                # Update document
DELETE /api/documents/{id}             # Delete document
```

**2. HTTP Status Codes**
```python
# Success codes
200: OK - Successful GET, PUT, PATCH
201: Created - Successful POST
204: No Content - Successful DELETE

# Client error codes
400: Bad Request - Invalid request format
401: Unauthorized - Authentication required
403: Forbidden - Access denied
404: Not Found - Resource doesn't exist
409: Conflict - Resource conflict (e.g., duplicate)
413: Payload Too Large - File size exceeds limit
422: Unprocessable Entity - Validation error
429: Too Many Requests - Rate limit exceeded

# Server error codes
500: Internal Server Error - Unexpected server error
503: Service Unavailable - Service temporarily unavailable
```

**3. Consistent Response Format**
```json
{
    "success": true,
    "message": "Operation completed successfully",
    "data": {
        // Actual response data
    },
    "pagination": {
        "page": 1,
        "per_page": 50,
        "total": 150,
        "pages": 3
    },
    "timestamp": "2025-08-09T10:30:00Z",
    "request_id": "req_1234567890"
}
```

### 2. WebSocket Architecture

```mermaid
graph TD
    subgraph "WebSocket Layer"
        WS_MANAGER[WebSocket Manager]
        CONNECTION_POOL[Connection Pool]
        MESSAGE_ROUTER[Message Router]
        EVENT_DISPATCHER[Event Dispatcher]
    end
    
    subgraph "Event Sources"
        DOC_EVENTS[Document Events]
        RAG_EVENTS[RAG Events]
        CITE_EVENTS[Citation Events]
        SYSTEM_EVENTS[System Events]
    end
    
    subgraph "Client Connections"
        CLIENT_1[Client 1]
        CLIENT_2[Client 2]
        CLIENT_N[Client N]
    end
    
    CLIENT_1 --> WS_MANAGER
    CLIENT_2 --> WS_MANAGER
    CLIENT_N --> WS_MANAGER
    
    WS_MANAGER --> CONNECTION_POOL
    CONNECTION_POOL --> MESSAGE_ROUTER
    MESSAGE_ROUTER --> EVENT_DISPATCHER
    
    DOC_EVENTS --> EVENT_DISPATCHER
    RAG_EVENTS --> EVENT_DISPATCHER
    CITE_EVENTS --> EVENT_DISPATCHER
    SYSTEM_EVENTS --> EVENT_DISPATCHER
```

#### WebSocket Event Types:

```python
class WebSocketEventType(Enum):
    # Connection events
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    PING = "ping"
    PONG = "pong"
    
    # Document events
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_UPDATED = "document.updated"
    DOCUMENT_DELETED = "document.deleted"
    
    # RAG events
    INDEX_BUILD_STARTED = "index.build_started"
    INDEX_BUILD_PROGRESS = "index.build_progress"
    INDEX_BUILD_COMPLETED = "index.build_completed"
    RAG_QUERY_STARTED = "rag.query_started"
    RAG_QUERY_PROGRESS = "rag.query_progress"
    RAG_QUERY_COMPLETED = "rag.query_completed"
    
    # Citation events
    CITATION_EXTRACTION_STARTED = "citations.extraction_started"
    CITATION_EXTRACTION_PROGRESS = "citations.extraction_progress"
    CITATION_EXTRACTION_COMPLETED = "citations.extraction_completed"
    
    # System events
    SYSTEM_STATUS_CHANGED = "system.status_changed"
    MAINTENANCE_MODE = "system.maintenance_mode"
    ERROR = "error"
```

## Service Layer Architecture

### 1. Service Composition

```mermaid
graph TD
    subgraph "Application Services"
        DOC_APP_SVC[Document Application Service]
        RAG_APP_SVC[RAG Application Service]
        CITE_APP_SVC[Citation Application Service]
        LIB_APP_SVC[Library Application Service]
    end
    
    subgraph "Domain Services"
        DOC_DOMAIN_SVC[Document Domain Service]
        RAG_DOMAIN_SVC[RAG Domain Service]
        CITE_DOMAIN_SVC[Citation Domain Service]
        SEARCH_DOMAIN_SVC[Search Domain Service]
    end
    
    subgraph "Infrastructure Services"
        FILE_SVC[File Service]
        CACHE_SVC[Cache Service]
        EVENT_SVC[Event Service]
        NOTIFICATION_SVC[Notification Service]
        VALIDATION_SVC[Validation Service]
    end
    
    DOC_APP_SVC --> DOC_DOMAIN_SVC
    RAG_APP_SVC --> RAG_DOMAIN_SVC
    CITE_APP_SVC --> CITE_DOMAIN_SVC
    LIB_APP_SVC --> SEARCH_DOMAIN_SVC
    
    DOC_DOMAIN_SVC --> FILE_SVC
    RAG_DOMAIN_SVC --> CACHE_SVC
    CITE_DOMAIN_SVC --> VALIDATION_SVC
    SEARCH_DOMAIN_SVC --> CACHE_SVC
    
    DOC_DOMAIN_SVC --> EVENT_SVC
    RAG_DOMAIN_SVC --> EVENT_SVC
    CITE_DOMAIN_SVC --> EVENT_SVC
    
    EVENT_SVC --> NOTIFICATION_SVC
```

### 2. Dependency Injection Pattern

```python
# Container configuration
class DIContainer:
    def __init__(self):
        self._services = {}
        self._configure_services()
    
    def _configure_services(self):
        # Repository layer
        self.register(IDocumentRepository, SQLiteDocumentRepository)
        self.register(ICitationRepository, SQLiteCitationRepository)
        self.register(IVectorRepository, ChromaVectorRepository)
        
        # Service layer
        self.register(IFileService, LocalFileService)
        self.register(ICacheService, RedisCacheService)
        self.register(IRAGService, LlamaIndexRAGService)
        
        # Application services
        self.register(DocumentService, lambda: DocumentService(
            self.get(IDocumentRepository),
            self.get(IFileService),
            self.get(ICacheService)
        ))
    
    def register(self, interface: Type, implementation: Union[Type, Callable]):
        self._services[interface] = implementation
    
    def get(self, interface: Type) -> Any:
        implementation = self._services.get(interface)
        if implementation is None:
            raise ValueError(f"Service {interface} not registered")
        
        if callable(implementation) and not isinstance(implementation, type):
            return implementation()
        
        return implementation()

# FastAPI dependency injection
def get_document_service() -> DocumentService:
    return container.get(DocumentService)

# Route handler with injected dependencies
@router.post("/documents/upload")
async def upload_document(
    file: UploadFile,
    document_service: DocumentService = Depends(get_document_service)
):
    return await document_service.upload_document(file)
```

## Frontend Architecture

### 1. React Application Structure

```mermaid
graph TD
    subgraph "React Application"
        APP[App Component]
        ROUTER[React Router]
        CONTEXT[Context Providers]
        LAYOUT[Layout Components]
    end
    
    subgraph "Feature Modules"
        DOCUMENTS[Documents Module]
        RAG[RAG Module]
        CITATIONS[Citations Module]
        LIBRARY[Library Module]
        SETTINGS[Settings Module]
    end
    
    subgraph "Shared Components"
        UI_COMPONENTS[UI Components]
        HOOKS[Custom Hooks]
        UTILS[Utilities]
        API_CLIENT[API Client]
    end
    
    subgraph "State Management"
        ZUSTAND[Zustand Stores]
        QUERY[React Query]
        LOCAL_STATE[Local State]
    end
    
    APP --> ROUTER
    APP --> CONTEXT
    ROUTER --> LAYOUT
    LAYOUT --> DOCUMENTS
    LAYOUT --> RAG
    LAYOUT --> CITATIONS
    LAYOUT --> LIBRARY
    LAYOUT --> SETTINGS
    
    DOCUMENTS --> UI_COMPONENTS
    RAG --> UI_COMPONENTS
    CITATIONS --> UI_COMPONENTS
    LIBRARY --> UI_COMPONENTS
    SETTINGS --> UI_COMPONENTS
    
    DOCUMENTS --> HOOKS
    RAG --> HOOKS
    CITATIONS --> HOOKS
    LIBRARY --> HOOKS
    
    HOOKS --> API_CLIENT
    HOOKS --> ZUSTAND
    HOOKS --> QUERY
    
    UI_COMPONENTS --> LOCAL_STATE
```

### 2. Component Architecture

```typescript
// Component hierarchy example
interface ComponentArchitecture {
    // Layout Components
    Layout: {
        Header: HeaderProps;
        Sidebar: SidebarProps;
        MainContent: MainContentProps;
        Footer: FooterProps;
    };
    
    // Feature Components
    Documents: {
        DocumentList: DocumentListProps;
        DocumentCard: DocumentCardProps;
        DocumentUpload: DocumentUploadProps;
        DocumentViewer: DocumentViewerProps;
    };
    
    // Shared Components
    UI: {
        Button: ButtonProps;
        Input: InputProps;
        Modal: ModalProps;
        Toast: ToastProps;
        Loading: LoadingProps;
    };
    
    // Business Components
    RAG: {
        QueryInterface: QueryInterfaceProps;
        ResponseDisplay: ResponseDisplayProps;
        SourceList: SourceListProps;
    };
}
```

### 3. State Management Strategy

```typescript
// Zustand store example
interface AppStore {
    // Document state
    documents: Document[];
    selectedDocument: Document | null;
    uploadProgress: UploadProgress | null;
    
    // RAG state
    queryHistory: RAGQuery[];
    currentQuery: string;
    queryResults: RAGResponse | null;
    
    // UI state
    sidebarOpen: boolean;
    theme: 'light' | 'dark';
    notifications: Notification[];
    
    // Actions
    setDocuments: (documents: Document[]) => void;
    selectDocument: (document: Document | null) => void;
    addQuery: (query: RAGQuery) => void;
    toggleSidebar: () => void;
    addNotification: (notification: Notification) => void;
}

// React Query for server state
const useDocuments = () => {
    return useQuery({
        queryKey: ['documents'],
        queryFn: () => api.getDocuments(),
        staleTime: 5 * 60 * 1000, // 5 minutes
        cacheTime: 10 * 60 * 1000, // 10 minutes
    });
};

const useUploadDocument = () => {
    const queryClient = useQueryClient();
    
    return useMutation({
        mutationFn: api.uploadDocument,
        onSuccess: () => {
            queryClient.invalidateQueries(['documents']);
        },
        onError: (error) => {
            toast.error(`Upload failed: ${error.message}`);
        },
    });
};
```

## Security Architecture

### 1. Security Layers

```mermaid
graph TD
    subgraph "Network Security"
        FIREWALL[Firewall]
        DDoS[DDoS Protection]
        TLS[TLS Encryption]
    end
    
    subgraph "Application Security"
        AUTH[Authentication]
        AUTHZ[Authorization]
        INPUT_VAL[Input Validation]
        OUTPUT_ENC[Output Encoding]
    end
    
    subgraph "Data Security"
        ENCRYPTION[Data Encryption]
        HASHING[Password Hashing]
        SANITIZATION[Data Sanitization]
        BACKUP_ENC[Backup Encryption]
    end
    
    subgraph "Infrastructure Security"
        CONTAINER_SEC[Container Security]
        SECRET_MGT[Secret Management]
        AUDIT_LOG[Audit Logging]
        MONITORING[Security Monitoring]
    end
    
    FIREWALL --> AUTH
    DDoS --> AUTH
    TLS --> AUTH
    
    AUTH --> AUTHZ
    AUTHZ --> INPUT_VAL
    INPUT_VAL --> OUTPUT_ENC
    
    OUTPUT_ENC --> ENCRYPTION
    ENCRYPTION --> HASHING
    HASHING --> SANITIZATION
    SANITIZATION --> BACKUP_ENC
    
    BACKUP_ENC --> CONTAINER_SEC
    CONTAINER_SEC --> SECRET_MGT
    SECRET_MGT --> AUDIT_LOG
    AUDIT_LOG --> MONITORING
```

### 2. Authentication & Authorization

```python
# Authentication system
class AuthenticationService:
    def __init__(
        self,
        jwt_service: JWTService,
        password_service: PasswordService,
        user_repository: IUserRepository
    ):
        self.jwt_service = jwt_service
        self.password_service = password_service
        self.user_repository = user_repository
    
    async def authenticate(self, username: str, password: str) -> AuthResult:
        # 1. Rate limiting check
        # 2. User lookup
        # 3. Password verification
        # 4. JWT token generation
        # 5. Session management
        pass
    
    async def verify_token(self, token: str) -> User:
        # 1. JWT signature verification
        # 2. Token expiration check
        # 3. User status verification
        # 4. Permission loading
        pass

# Authorization decorators
@require_permission("documents:read")
async def get_document(document_id: int, current_user: User = Depends(get_current_user)):
    pass

@require_role("admin")
async def delete_all_documents(current_user: User = Depends(get_current_user)):
    pass
```

### 3. Input Validation & Sanitization

```python
# Pydantic models for validation
class DocumentUploadRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=255, min_length=1)
    tags: Optional[List[str]] = Field(None, max_items=10)
    check_duplicates: bool = Field(True)
    
    @validator('title')
    def validate_title(cls, v):
        if v is not None:
            # Remove dangerous characters
            v = re.sub(r'[<>"\']', '', v)
            # Trim whitespace
            v = v.strip()
        return v
    
    @validator('tags')
    def validate_tags(cls, v):
        if v is not None:
            # Sanitize each tag
            v = [re.sub(r'[<>"\']', '', tag.strip()) for tag in v]
            # Remove empty tags
            v = [tag for tag in v if tag]
        return v

# SQL injection prevention
class DocumentRepository:
    async def search_documents(self, query: str) -> List[Document]:
        # Use parameterized queries
        stmt = select(DocumentModel).where(
            DocumentModel.title.contains(query) |
            DocumentModel.content.contains(query)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
```

## Deployment Architecture

### 1. Container Architecture

```mermaid
graph TD
    subgraph "Docker Containers"
        WEB[Web Container]
        API[API Container]
        WORKER[Worker Container]
        DB[Database Container]
        CACHE[Cache Container]
        NGINX[Nginx Container]
    end
    
    subgraph "Volumes"
        DOCS[Documents Volume]
        DB_DATA[Database Volume]
        CACHE_DATA[Cache Volume]
        LOGS[Logs Volume]
    end
    
    subgraph "Networks"
        FRONTEND_NET[Frontend Network]
        BACKEND_NET[Backend Network]
        DB_NET[Database Network]
    end
    
    NGINX --> WEB
    NGINX --> API
    WEB --> FRONTEND_NET
    API --> BACKEND_NET
    WORKER --> BACKEND_NET
    
    DB --> DB_NET
    CACHE --> DB_NET
    
    API --> DOCS
    WORKER --> DOCS
    DB --> DB_DATA
    CACHE --> CACHE_DATA
    
    API --> LOGS
    WORKER --> LOGS
    NGINX --> LOGS
```

### 2. Kubernetes Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pdf-scholar-api
  labels:
    app: pdf-scholar-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: pdf-scholar-api
  template:
    metadata:
      labels:
        app: pdf-scholar-api
    spec:
      containers:
      - name: api
        image: pdf-scholar-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: pdf-scholar-secrets
              key: database-url
        - name: GEMINI_API_KEY
          valueFrom:
            secretKeyRef:
              name: pdf-scholar-secrets
              key: gemini-api-key
        volumeMounts:
        - name: documents-storage
          mountPath: /app/documents
        - name: logs-storage
          mountPath: /app/logs
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /api/system/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/system/health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: documents-storage
        persistentVolumeClaim:
          claimName: documents-pvc
      - name: logs-storage
        persistentVolumeClaim:
          claimName: logs-pvc
```

### 3. Infrastructure as Code

```terraform
# terraform/main.tf
resource "aws_ecs_cluster" "pdf_scholar_cluster" {
  name = "pdf-scholar"
  
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_service" "pdf_scholar_api" {
  name            = "pdf-scholar-api"
  cluster         = aws_ecs_cluster.pdf_scholar_cluster.id
  task_definition = aws_ecs_task_definition.pdf_scholar_api.arn
  desired_count   = 3
  
  load_balancer {
    target_group_arn = aws_lb_target_group.pdf_scholar_api.arn
    container_name   = "api"
    container_port   = 8000
  }
  
  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.pdf_scholar_api.id]
    assign_public_ip = false
  }
  
  service_registries {
    registry_arn = aws_service_discovery_service.pdf_scholar_api.arn
  }
}

resource "aws_ecs_task_definition" "pdf_scholar_api" {
  family                   = "pdf-scholar-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn
  
  container_definitions = jsonencode([
    {
      name  = "api"
      image = "your-registry/pdf-scholar-api:latest"
      
      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]
      
      environment = [
        {
          name  = "ENVIRONMENT"
          value = "production"
        }
      ]
      
      secrets = [
        {
          name      = "DATABASE_URL"
          valueFrom = aws_ssm_parameter.database_url.arn
        },
        {
          name      = "GEMINI_API_KEY"
          valueFrom = aws_ssm_parameter.gemini_api_key.arn
        }
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.pdf_scholar_api.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
      
      healthCheck = {
        command = [
          "CMD-SHELL",
          "curl -f http://localhost:8000/api/system/health || exit 1"
        ]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])
}
```

## Performance & Scalability

### 1. Performance Architecture

```mermaid
graph TD
    subgraph "Performance Optimization"
        CACHING[Multi-Level Caching]
        CONNECTION_POOL[Database Connection Pooling]
        LAZY_LOADING[Lazy Loading]
        PAGINATION[Efficient Pagination]
        COMPRESSION[Response Compression]
    end
    
    subgraph "Scalability Patterns"
        HORIZONTAL[Horizontal Scaling]
        LOAD_BALANCING[Load Balancing]
        AUTO_SCALING[Auto Scaling]
        CDN[Content Delivery Network]
        ASYNC_PROCESSING[Async Processing]
    end
    
    subgraph "Monitoring"
        APM[Application Performance Monitoring]
        METRICS[Metrics Collection]
        ALERTING[Performance Alerting]
        PROFILING[Performance Profiling]
    end
    
    CACHING --> HORIZONTAL
    CONNECTION_POOL --> HORIZONTAL
    LAZY_LOADING --> HORIZONTAL
    PAGINATION --> HORIZONTAL
    COMPRESSION --> HORIZONTAL
    
    HORIZONTAL --> APM
    LOAD_BALANCING --> APM
    AUTO_SCALING --> APM
    CDN --> APM
    ASYNC_PROCESSING --> APM
    
    APM --> METRICS
    METRICS --> ALERTING
    ALERTING --> PROFILING
```

### 2. Caching Strategy

```python
# Multi-level caching implementation
class CacheManager:
    def __init__(
        self,
        l1_cache: InMemoryCache,
        l2_cache: RedisCache,
        l3_cache: DatabaseCache
    ):
        self.l1 = l1_cache
        self.l2 = l2_cache
        self.l3 = l3_cache
    
    async def get(self, key: str) -> Optional[Any]:
        # L1 cache (fastest)
        value = await self.l1.get(key)
        if value is not None:
            return value
        
        # L2 cache (distributed)
        value = await self.l2.get(key)
        if value is not None:
            await self.l1.set(key, value, ttl=300)  # 5 minutes
            return value
        
        # L3 cache (database query cache)
        value = await self.l3.get(key)
        if value is not None:
            await self.l2.set(key, value, ttl=3600)  # 1 hour
            await self.l1.set(key, value, ttl=300)   # 5 minutes
            return value
        
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600):
        await self.l1.set(key, value, min(ttl, 300))
        await self.l2.set(key, value, ttl)
        # L3 is populated on cache miss

# Cache decorators
@cache_result(ttl=300, cache_key_template="document:{document_id}")
async def get_document(document_id: int) -> Document:
    return await document_repository.get_by_id(document_id)

@cache_result(ttl=3600, cache_key_template="documents:list:{page}:{per_page}")
async def list_documents(page: int = 1, per_page: int = 50) -> DocumentList:
    return await document_repository.list_paginated(page, per_page)
```

### 3. Database Optimization

```python
# Connection pooling
DATABASE_CONFIG = {
    "pool_size": 10,
    "max_overflow": 20,
    "pool_timeout": 30,
    "pool_recycle": 3600,
    "pool_pre_ping": True,
}

# Query optimization
class OptimizedDocumentRepository:
    async def search_documents_with_citations(
        self, 
        query: str, 
        page: int = 1, 
        per_page: int = 50
    ) -> DocumentSearchResult:
        # Use joins instead of N+1 queries
        stmt = (
            select(DocumentModel, func.count(CitationModel.id).label('citation_count'))
            .outerjoin(CitationModel, DocumentModel.id == CitationModel.document_id)
            .where(
                or_(
                    DocumentModel.title.contains(query),
                    DocumentModel.content.contains(query)
                )
            )
            .group_by(DocumentModel.id)
            .options(
                # Eager load related data
                selectinload(DocumentModel.metadata),
                selectinload(DocumentModel.tags)
            )
            .limit(per_page)
            .offset((page - 1) * per_page)
        )
        
        result = await self.db.execute(stmt)
        return result.fetchall()
    
    # Batch operations
    async def bulk_update_access_time(self, document_ids: List[int]):
        stmt = (
            update(DocumentModel)
            .where(DocumentModel.id.in_(document_ids))
            .values(last_accessed=func.now())
        )
        await self.db.execute(stmt)
```

## Monitoring & Observability

### 1. Monitoring Architecture

```mermaid
graph TD
    subgraph "Application Metrics"
        REQUEST_METRICS[Request Metrics]
        RESPONSE_METRICS[Response Times]
        ERROR_METRICS[Error Rates]
        BUSINESS_METRICS[Business Metrics]
    end
    
    subgraph "Infrastructure Metrics"
        CPU_METRICS[CPU Usage]
        MEMORY_METRICS[Memory Usage]
        DISK_METRICS[Disk I/O]
        NETWORK_METRICS[Network I/O]
    end
    
    subgraph "Logging"
        APP_LOGS[Application Logs]
        ACCESS_LOGS[Access Logs]
        ERROR_LOGS[Error Logs]
        AUDIT_LOGS[Audit Logs]
    end
    
    subgraph "Monitoring Stack"
        PROMETHEUS[Prometheus]
        GRAFANA[Grafana]
        ELASTICSEARCH[Elasticsearch]
        KIBANA[Kibana]
        JAEGER[Jaeger Tracing]
    end
    
    REQUEST_METRICS --> PROMETHEUS
    RESPONSE_METRICS --> PROMETHEUS
    ERROR_METRICS --> PROMETHEUS
    BUSINESS_METRICS --> PROMETHEUS
    
    CPU_METRICS --> PROMETHEUS
    MEMORY_METRICS --> PROMETHEUS
    DISK_METRICS --> PROMETHEUS
    NETWORK_METRICS --> PROMETHEUS
    
    PROMETHEUS --> GRAFANA
    
    APP_LOGS --> ELASTICSEARCH
    ACCESS_LOGS --> ELASTICSEARCH
    ERROR_LOGS --> ELASTICSEARCH
    AUDIT_LOGS --> ELASTICSEARCH
    
    ELASTICSEARCH --> KIBANA
    
    REQUEST_METRICS --> JAEGER
    RESPONSE_METRICS --> JAEGER
```

### 2. Metrics Collection

```python
# Prometheus metrics
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Custom metrics
REQUEST_COUNT = Counter(
    'pdf_scholar_requests_total',
    'Total requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'pdf_scholar_request_duration_seconds',
    'Request duration',
    ['method', 'endpoint']
)

ACTIVE_CONNECTIONS = Gauge(
    'pdf_scholar_active_connections',
    'Active WebSocket connections'
)

DOCUMENT_COUNT = Gauge(
    'pdf_scholar_documents_total',
    'Total documents in system'
)

RAG_QUERY_COUNT = Counter(
    'pdf_scholar_rag_queries_total',
    'Total RAG queries',
    ['status']
)

# Metrics middleware
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    REQUEST_DURATION.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)
    
    return response

# Business metrics
class BusinessMetricsCollector:
    def __init__(self):
        self.document_uploads = Counter('documents_uploaded_total')
        self.rag_queries = Counter('rag_queries_total', ['success'])
        self.citation_extractions = Counter('citation_extractions_total')
        self.user_sessions = Counter('user_sessions_total')
    
    def record_document_upload(self):
        self.document_uploads.inc()
    
    def record_rag_query(self, success: bool):
        self.rag_queries.labels(success=str(success).lower()).inc()
    
    def record_citation_extraction(self, citation_count: int):
        self.citation_extractions.inc(citation_count)
```

### 3. Distributed Tracing

```python
# OpenTelemetry configuration
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Initialize tracing
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# Configure exporters
jaeger_exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=6831,
)

span_processor = BatchSpanProcessor(jaeger_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Auto-instrument frameworks
FastAPIInstrumentor.instrument_app(app)
SQLAlchemyInstrumentor().instrument(engine=engine)
RedisInstrumentor().instrument()

# Manual instrumentation for business logic
class DocumentService:
    async def upload_document(self, file_data: bytes, metadata: DocumentMetadata) -> Document:
        with tracer.start_as_current_span("document_upload") as span:
            span.set_attribute("file_size", len(file_data))
            span.set_attribute("file_type", metadata.file_type)
            
            # Content extraction
            with tracer.start_as_current_span("content_extraction"):
                content = await self._extract_content(file_data)
                span.set_attribute("extracted_content_length", len(content))
            
            # Hash generation
            with tracer.start_as_current_span("hash_generation"):
                file_hash = await self._generate_hash(file_data)
                content_hash = await self._generate_hash(content)
            
            # Duplicate check
            with tracer.start_as_current_span("duplicate_check"):
                is_duplicate = await self._check_duplicates(content_hash)
                span.set_attribute("is_duplicate", is_duplicate)
            
            if is_duplicate:
                span.record_exception(DuplicateDocumentError())
                raise DuplicateDocumentError()
            
            # Database save
            with tracer.start_as_current_span("database_save"):
                document = await self.repository.create(Document(
                    title=metadata.title,
                    content_hash=content_hash,
                    file_hash=file_hash,
                    content=content
                ))
            
            span.set_attribute("document_id", document.id)
            return document
```

## Future Architecture

### 1. Microservices Evolution

```mermaid
graph TD
    subgraph "Current Monolith"
        CURRENT[PDF Scholar Monolith]
    end
    
    subgraph "Future Microservices"
        GATEWAY[API Gateway]
        DOC_SVC[Document Service]
        RAG_SVC[RAG Service]
        CITE_SVC[Citation Service]
        USER_SVC[User Service]
        SEARCH_SVC[Search Service]
        NOTIFICATION_SVC[Notification Service]
    end
    
    subgraph "Shared Infrastructure"
        MESSAGE_BUS[Message Bus]
        CONFIG_SVC[Configuration Service]
        MONITORING[Monitoring Service]
        TRACING[Tracing Service]
    end
    
    CURRENT -.-> GATEWAY
    
    GATEWAY --> DOC_SVC
    GATEWAY --> RAG_SVC
    GATEWAY --> CITE_SVC
    GATEWAY --> USER_SVC
    GATEWAY --> SEARCH_SVC
    
    DOC_SVC --> MESSAGE_BUS
    RAG_SVC --> MESSAGE_BUS
    CITE_SVC --> MESSAGE_BUS
    SEARCH_SVC --> MESSAGE_BUS
    NOTIFICATION_SVC --> MESSAGE_BUS
    
    DOC_SVC --> CONFIG_SVC
    RAG_SVC --> CONFIG_SVC
    CITE_SVC --> CONFIG_SVC
    
    ALL_SERVICES --> MONITORING
    ALL_SERVICES --> TRACING
```

### 2. AI/ML Pipeline Architecture

```mermaid
graph TD
    subgraph "ML Pipeline"
        DATA_INGESTION[Data Ingestion]
        FEATURE_EXTRACTION[Feature Extraction]
        MODEL_TRAINING[Model Training]
        MODEL_DEPLOYMENT[Model Deployment]
        MODEL_SERVING[Model Serving]
    end
    
    subgraph "AI Services"
        EMBEDDING_SVC[Embedding Service]
        CLASSIFICATION_SVC[Document Classification]
        SUMMARIZATION_SVC[Summarization Service]
        RECOMMENDATION_SVC[Recommendation Service]
        QA_SVC[Question Answering]
    end
    
    subgraph "Model Registry"
        EMBEDDING_MODELS[Embedding Models]
        CLASSIFICATION_MODELS[Classification Models]
        GENERATION_MODELS[Generation Models]
        CUSTOM_MODELS[Custom Models]
    end
    
    DATA_INGESTION --> FEATURE_EXTRACTION
    FEATURE_EXTRACTION --> MODEL_TRAINING
    MODEL_TRAINING --> MODEL_DEPLOYMENT
    MODEL_DEPLOYMENT --> MODEL_SERVING
    
    MODEL_SERVING --> EMBEDDING_SVC
    MODEL_SERVING --> CLASSIFICATION_SVC
    MODEL_SERVING --> SUMMARIZATION_SVC
    MODEL_SERVING --> RECOMMENDATION_SVC
    MODEL_SERVING --> QA_SVC
    
    MODEL_DEPLOYMENT --> EMBEDDING_MODELS
    MODEL_DEPLOYMENT --> CLASSIFICATION_MODELS
    MODEL_DEPLOYMENT --> GENERATION_MODELS
    MODEL_DEPLOYMENT --> CUSTOM_MODELS
```

### 3. Multi-Tenant Architecture

```mermaid
graph TD
    subgraph "Multi-Tenant Layer"
        TENANT_ROUTER[Tenant Router]
        TENANT_ISOLATION[Tenant Isolation]
        TENANT_CONFIG[Tenant Configuration]
    end
    
    subgraph "Tenant A"
        A_DB[(Tenant A Database)]
        A_STORAGE[(Tenant A Storage)]
        A_CACHE[(Tenant A Cache)]
    end
    
    subgraph "Tenant B"  
        B_DB[(Tenant B Database)]
        B_STORAGE[(Tenant B Storage)]
        B_CACHE[(Tenant B Cache)]
    end
    
    subgraph "Shared Services"
        SHARED_AI[Shared AI Services]
        SHARED_MONITORING[Shared Monitoring]
        SHARED_LOGGING[Shared Logging]
    end
    
    TENANT_ROUTER --> TENANT_ISOLATION
    TENANT_ISOLATION --> TENANT_CONFIG
    
    TENANT_CONFIG --> A_DB
    TENANT_CONFIG --> A_STORAGE
    TENANT_CONFIG --> A_CACHE
    
    TENANT_CONFIG --> B_DB
    TENANT_CONFIG --> B_STORAGE
    TENANT_CONFIG --> B_CACHE
    
    A_DB --> SHARED_AI
    B_DB --> SHARED_AI
    
    A_DB --> SHARED_MONITORING
    B_DB --> SHARED_MONITORING
    
    A_DB --> SHARED_LOGGING
    B_DB --> SHARED_LOGGING
```

### 4. Edge Computing Architecture

```mermaid
graph TD
    subgraph "Cloud Core"
        CLOUD_API[Cloud API]
        CLOUD_DB[(Cloud Database)]
        CLOUD_ML[Cloud ML Services]
    end
    
    subgraph "Edge Nodes"
        EDGE_1[Edge Node 1]
        EDGE_2[Edge Node 2]
        EDGE_3[Edge Node 3]
    end
    
    subgraph "Edge Capabilities"
        LOCAL_PROCESSING[Local Document Processing]
        EDGE_CACHE[Edge Cache]
        OFFLINE_MODE[Offline Mode]
        DATA_SYNC[Data Synchronization]
    end
    
    CLOUD_API --> EDGE_1
    CLOUD_API --> EDGE_2
    CLOUD_API --> EDGE_3
    
    EDGE_1 --> LOCAL_PROCESSING
    EDGE_1 --> EDGE_CACHE
    EDGE_1 --> OFFLINE_MODE
    EDGE_1 --> DATA_SYNC
    
    EDGE_2 --> LOCAL_PROCESSING
    EDGE_2 --> EDGE_CACHE
    EDGE_2 --> OFFLINE_MODE
    EDGE_2 --> DATA_SYNC
    
    EDGE_3 --> LOCAL_PROCESSING
    EDGE_3 --> EDGE_CACHE
    EDGE_3 --> OFFLINE_MODE
    EDGE_3 --> DATA_SYNC
    
    DATA_SYNC --> CLOUD_DB
    LOCAL_PROCESSING --> CLOUD_ML
```

---

**Architecture Version**: 2.1.0  
**Last Updated**: 2025-08-09  
**Status**: Current Architecture  
**Next Review**: 2025-12-01  

This architecture documentation provides a comprehensive overview of the AI Enhanced PDF Scholar system design, from high-level principles to detailed implementation patterns. The architecture supports the current single-user deployment while being designed for future scalability and multi-tenant scenarios.