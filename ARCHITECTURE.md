# System Architecture & Design

This document provides an overview of the system architecture for the AI Enhanced PDF Scholar platform. It includes a high-level component diagram and a data flow diagram for the core user workflow.

---

## 1. High-Level System Architecture

This diagram illustrates the major components of the platform and their interactions. The system is designed with a modern, scalable architecture, separating concerns between the frontend, backend services, and data storage.

```mermaid
graph TD;
    subgraph "User-Facing Layer"
        WebApp[React Frontend];
    end

    subgraph "Backend Services (FastAPI)"
        APIGateway[API Gateway];
        AuthService[Auth Service];
        DocService[Document Service];
        RAGService[RAG & Citation Service];
    end

    subgraph "Data & AI Layer"
        PostgresDB[(PostgreSQL Database)];
        VectorStore[(Vector Store - LlamaIndex)];
        GeminiAPI[External: Google Gemini API];
    end

    WebApp --> APIGateway;
    APIGateway --> AuthService;
    APIGateway --> DocService;
    APIGateway --> RAGService;

    AuthService -- Manages Users --> PostgresDB;
    DocService -- Manages Documents & Metadata --> PostgresDB;
    RAGService -- Stores & Retrieves Embeddings --> VectorStore;
    RAGService -- Retrieves Document Info --> DocService;
    RAGService -- Augments Prompts & Queries --> GeminiAPI;
```

### Component Descriptions:
- **React Frontend:** A modern, responsive single-page application that provides the user interface.
- **API Gateway:** The single entry point for all client requests, routing them to the appropriate backend service.
- **Auth Service:** Handles user registration, login, and JWT-based session management.
- **Document Service:** Manages the lifecycle of documents, including uploads, storage, and metadata management.
- **RAG & Citation Service:** The core AI engine. It handles PDF parsing, vector embedding creation, similarity search, and interaction with the external LLM.
- **PostgreSQL Database:** The primary relational database for storing user data, document metadata, and citation information.
- **Vector Store:** A specialized database (managed by LlamaIndex) optimized for storing and querying high-dimensional vector embeddings.
- **Google Gemini API:** The external Large Language Model used for the "generation" part of RAG.

---

## 2. Data Flow Diagram: Core RAG Workflow

This sequence diagram details the process of a user asking a question about a specific document. This is the primary value-add workflow of the platform.

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant BackendAPI as "Backend API"
    participant RAGService as "RAG Service"
    participant VectorStore as "Vector Store"
    participant GeminiAPI as "Google Gemini API"

    User->>Frontend: Selects document and asks a question
    Frontend->>BackendAPI: POST /api/rag/query (documentId, query)
    BackendAPI->>RAGService: process_query(documentId, query)

    RAGService->>VectorStore: Retrieve relevant text chunks for documentId and query
    VectorStore-->>RAGService: Returns top-k similar chunks

    RAGService->>RAGService: Augment prompt with retrieved chunks and original query
    RAGService->>GeminiAPI: Send augmented prompt

    GeminiAPI-->>RAGService: Return generated answer

    RAGService-->>BackendAPI: Return final answer with sources
    BackendAPI-->>Frontend: 200 OK with { "answer": "...", "sources": [...] }
    Frontend-->>User: Displays the answer and source snippets
```

This flow demonstrates how we combine the user's query with relevant, retrieved context from their own documents before sending it to the LLM. This ensures that the answers are grounded in the provided source material, making them accurate and verifiable.
