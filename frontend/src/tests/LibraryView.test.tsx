import type { ReactElement } from 'react'
import { describe, expect, it, beforeEach, vi, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

import LibraryView from '../components/views/LibraryView'
import { api } from '../lib/api'
import type { DocumentListResponse, Document } from '../types'

// Mock the API module
vi.mock('../lib/api', () => ({
  api: {
    getDocuments: vi.fn(),
  },
}))

const mockedGetDocuments = vi.mocked(api.getDocuments)

// Mock lazy-loaded DocumentUpload component
vi.mock('../components/DocumentUpload', () => ({
  default: ({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) => (
    <div data-testid="document-upload">
      <button onClick={onClose}>Close Upload</button>
      <button onClick={onSuccess}>Upload Success</button>
    </div>
  ),
}))

const createMockDocuments = (count: number): Document[] => {
  return Array.from({ length: count }, (_, i) => ({
    id: i + 1,
    title: `Document ${i + 1}.pdf`,
    file_path: `/tmp/doc${i + 1}.pdf`,
    file_hash: `hash-${i + 1}`,
    file_size: 1024 * (i + 1),
    page_count: (i % 10) + 1,
    preview_url: `/api/documents/${i + 1}/preview`,
    thumbnail_url: `/api/documents/${i + 1}/thumbnail`,
    created_at: new Date(Date.now() - i * 86400000).toISOString(),
    updated_at: new Date(Date.now() - i * 3600000).toISOString(),
    last_accessed: i % 3 === 0 ? new Date().toISOString() : null,
    metadata: null,
    is_file_available: i % 5 !== 0,
    content_hash: null,
    _links: {
      self: `/api/documents/${i + 1}`,
      related: {
        download: `/api/documents/${i + 1}/download`,
      },
    },
  }))
}

const createMockResponse = (docs: Document[], page = 1, perPage = 20, total?: number): DocumentListResponse => ({
  success: true,
  data: docs,
  meta: {
    timestamp: new Date().toISOString(),
    version: 'v2',
    request_id: 'test',
    page,
    per_page: perPage,
    total: total ?? docs.length,
    total_pages: Math.ceil((total ?? docs.length) / perPage),
    has_next: page * perPage < (total ?? docs.length),
    has_prev: page > 1,
  },
  errors: null,
})

function renderWithProviders(ui: ReactElement, queryClient?: QueryClient) {
  const client = queryClient ?? new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('LibraryView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('Initial Load', () => {
    it('displays loading state initially', () => {
      mockedGetDocuments.mockImplementation(() => new Promise(() => {}))

      renderWithProviders(<LibraryView />)

      expect(document.querySelector('.animate-spin')).toBeInTheDocument()
    })

    it('displays documents after loading', async () => {
      const docs = createMockDocuments(5)
      mockedGetDocuments.mockResolvedValue(createMockResponse(docs))

      renderWithProviders(<LibraryView />)

      await waitFor(() => {
        expect(screen.getByText('Document 1.pdf')).toBeInTheDocument()
      })

      expect(screen.getByText('5 documents')).toBeInTheDocument()
    })

    it('displays empty state when no documents', async () => {
      mockedGetDocuments.mockResolvedValue(createMockResponse([]))

      renderWithProviders(<LibraryView />)

      await waitFor(() => {
        expect(screen.getByText(/no documents found/i)).toBeInTheDocument()
      })

      expect(screen.getByText(/start by uploading your first document/i)).toBeInTheDocument()
    })

    it('displays error state on fetch failure', async () => {
      mockedGetDocuments.mockRejectedValue(new Error('Network error'))

      renderWithProviders(<LibraryView />)

      await waitFor(() => {
        expect(screen.getByText(/failed to load documents/i)).toBeInTheDocument()
      })

      expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
    })

    it('retries fetching when clicking try again', async () => {
      mockedGetDocuments.mockRejectedValueOnce(new Error('Network error'))
      const docs = createMockDocuments(3)
      mockedGetDocuments.mockResolvedValueOnce(createMockResponse(docs))

      renderWithProviders(<LibraryView />)

      await waitFor(() => {
        expect(screen.getByText(/failed to load documents/i)).toBeInTheDocument()
      })

      const tryAgainButton = screen.getByRole('button', { name: /try again/i })
      fireEvent.click(tryAgainButton)

      await waitFor(() => {
        expect(screen.getByText('Document 1.pdf')).toBeInTheDocument()
      })
    })
  })

  describe('Search Functionality', () => {
    it('searches documents with query', async () => {
      const docs = createMockDocuments(3)
      mockedGetDocuments.mockResolvedValue(createMockResponse(docs))

      renderWithProviders(<LibraryView />)

      await waitFor(() => {
        expect(screen.getByText('Document 1.pdf')).toBeInTheDocument()
      })

      const searchInput = screen.getByPlaceholderText(/search documents/i)
      fireEvent.change(searchInput, { target: { value: 'search query' } })

      await waitFor(() => {
        expect(mockedGetDocuments).toHaveBeenCalledWith(
          expect.objectContaining({ query: 'search query', page: 1 })
        )
      })
    })

    it('resets to page 1 when searching', async () => {
      const docs = createMockDocuments(25)
      mockedGetDocuments.mockResolvedValue(createMockResponse(docs, 2, 20, 25))

      renderWithProviders(<LibraryView />)

      await waitFor(() => {
        expect(screen.getByText(/page 2 of 2/i)).toBeInTheDocument()
      })

      const searchInput = screen.getByPlaceholderText(/search documents/i)
      fireEvent.change(searchInput, { target: { value: 'test' } })

      await waitFor(() => {
        expect(mockedGetDocuments).toHaveBeenLastCalledWith(
          expect.objectContaining({ page: 1 })
        )
      })
    })
  })

  describe('View Mode Toggle', () => {
    it('switches between grid and list views', async () => {
      const docs = createMockDocuments(3)
      mockedGetDocuments.mockResolvedValue(createMockResponse(docs))

      renderWithProviders(<LibraryView />)

      await waitFor(() => {
        expect(screen.getByText('Document 1.pdf')).toBeInTheDocument()
      })

      // Initially in grid view - cards should be in grid container
      expect(document.querySelector('.document-grid')).toBeInTheDocument()

      // Switch to list view
      const viewToggle = screen.getByRole('button', { name: /switch to list view/i })
      fireEvent.click(viewToggle)

      await waitFor(() => {
        // After clicking, the component should update
        expect(screen.getByText('Document 1.pdf')).toBeInTheDocument()
      })
    })
  })

  describe('Sorting', () => {
    it('changes sort order via dropdown', async () => {
      const docs = createMockDocuments(3)
      mockedGetDocuments.mockResolvedValue(createMockResponse(docs))

      renderWithProviders(<LibraryView />)

      await waitFor(() => {
        expect(screen.getByText('Document 1.pdf')).toBeInTheDocument()
      })

      const sortSelect = screen.getByDisplayValue(/recently updated/i)
      fireEvent.change(sortSelect, { target: { value: 'title_asc' } })

      await waitFor(() => {
        expect(mockedGetDocuments).toHaveBeenCalledWith(
          expect.objectContaining({ sort_by: 'title', sort_order: 'asc' })
        )
      })
    })

    it('supports all sort options', async () => {
      const docs = createMockDocuments(3)
      mockedGetDocuments.mockResolvedValue(createMockResponse(docs))

      renderWithProviders(<LibraryView />)

      await waitFor(() => {
        expect(screen.getByText('Document 1.pdf')).toBeInTheDocument()
      })

      const sortSelect = screen.getByDisplayValue(/recently updated/i)
      
      // Test various sort options
      const sortOptions = [
        { value: 'created_at_desc', sort_by: 'created_at', sort_order: 'desc' },
        { value: 'title_asc', sort_by: 'title', sort_order: 'asc' },
        { value: 'title_desc', sort_by: 'title', sort_order: 'desc' },
        { value: 'file_size_desc', sort_by: 'file_size', sort_order: 'desc' },
      ]

      for (const option of sortOptions) {
        fireEvent.change(sortSelect, { target: { value: option.value } })
        
        await waitFor(() => {
          expect(mockedGetDocuments).toHaveBeenCalledWith(
            expect.objectContaining({
              sort_by: option.sort_by,
              sort_order: option.sort_order,
            })
          )
        })
      }
    })
  })

  describe('Pagination', () => {
    it('displays pagination when there are multiple pages', async () => {
      const docs = createMockDocuments(25)
      mockedGetDocuments.mockResolvedValue(createMockResponse(docs, 1, 20, 25))

      renderWithProviders(<LibraryView />)

      await waitFor(() => {
        expect(screen.getByText(/page 1 of 2/i)).toBeInTheDocument()
      })

      expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument()
    })

    it('navigates to next page', async () => {
      const docs = createMockDocuments(25)
      mockedGetDocuments.mockResolvedValue(createMockResponse(docs, 1, 20, 25))

      renderWithProviders(<LibraryView />)

      await waitFor(() => {
        expect(screen.getByText(/page 1 of 2/i)).toBeInTheDocument()
      })

      const nextButton = screen.getByRole('button', { name: /next/i })
      fireEvent.click(nextButton)

      await waitFor(() => {
        expect(mockedGetDocuments).toHaveBeenCalledWith(
          expect.objectContaining({ page: 2 })
        )
      })
    })

    it('disables previous button on first page', async () => {
      const docs = createMockDocuments(25)
      mockedGetDocuments.mockResolvedValue(createMockResponse(docs, 1, 20, 25))

      renderWithProviders(<LibraryView />)

      await waitFor(() => {
        expect(screen.getByText(/page 1 of 2/i)).toBeInTheDocument()
      })

      const prevButton = screen.getByRole('button', { name: /previous/i })
      expect(prevButton).toBeDisabled()
    })

    it('disables next button on last page', async () => {
      const docs = createMockDocuments(25)
      mockedGetDocuments.mockResolvedValue(createMockResponse(docs, 2, 20, 25))

      renderWithProviders(<LibraryView />)

      await waitFor(() => {
        expect(screen.getByText(/page 2 of 2/i)).toBeInTheDocument()
      })

      const nextButton = screen.getByRole('button', { name: /next/i })
      expect(nextButton).toBeDisabled()
    })

    it('hides pagination when only one page', async () => {
      const docs = createMockDocuments(5)
      mockedGetDocuments.mockResolvedValue(createMockResponse(docs))

      renderWithProviders(<LibraryView />)

      await waitFor(() => {
        expect(screen.getByText('Document 1.pdf')).toBeInTheDocument()
      })

      expect(screen.queryByRole('button', { name: /next/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /previous/i })).not.toBeInTheDocument()
    })
  })

  describe('Upload Modal', () => {
    it('opens upload modal when clicking add document', async () => {
      const docs = createMockDocuments(3)
      mockedGetDocuments.mockResolvedValue(createMockResponse(docs))

      renderWithProviders(<LibraryView />)

      await waitFor(() => {
        expect(screen.getByText('Document 1.pdf')).toBeInTheDocument()
      })

      const addButton = screen.getByRole('button', { name: /add document/i })
      fireEvent.click(addButton)

      expect(screen.getByTestId('document-upload')).toBeInTheDocument()
    })

    it('opens upload modal from empty state', async () => {
      mockedGetDocuments.mockResolvedValue(createMockResponse([]))

      renderWithProviders(<LibraryView />)

      await waitFor(() => {
        expect(screen.getByText(/no documents found/i)).toBeInTheDocument()
      })

      const uploadButton = screen.getByRole('button', { name: /upload document/i })
      fireEvent.click(uploadButton)

      expect(screen.getByTestId('document-upload')).toBeInTheDocument()
    })

    it('closes upload modal', async () => {
      const docs = createMockDocuments(3)
      mockedGetDocuments.mockResolvedValue(createMockResponse(docs))

      renderWithProviders(<LibraryView />)

      await waitFor(() => {
        expect(screen.getByText('Document 1.pdf')).toBeInTheDocument()
      })

      // Open modal
      const addButton = screen.getByRole('button', { name: /add document/i })
      fireEvent.click(addButton)

      expect(screen.getByTestId('document-upload')).toBeInTheDocument()

      // Close modal
      const closeButton = screen.getByRole('button', { name: /close upload/i })
      fireEvent.click(closeButton)

      await waitFor(() => {
        expect(screen.queryByTestId('document-upload')).not.toBeInTheDocument()
      })
    })

    it('refreshes document list after successful upload', async () => {
      const docs = createMockDocuments(3)
      mockedGetDocuments.mockResolvedValue(createMockResponse(docs))

      renderWithProviders(<LibraryView />)

      await waitFor(() => {
        expect(screen.getByText('Document 1.pdf')).toBeInTheDocument()
      })

      // Open modal
      const addButton = screen.getByRole('button', { name: /add document/i })
      fireEvent.click(addButton)

      // Trigger success
      const successButton = screen.getByRole('button', { name: /upload success/i })
      fireEvent.click(successButton)

      await waitFor(() => {
        expect(mockedGetDocuments).toHaveBeenCalledTimes(2) // Initial + after success
      })
    })
  })

  describe('Header', () => {
    it('displays correct document count', async () => {
      const docs = createMockDocuments(42)
      mockedGetDocuments.mockResolvedValue(createMockResponse(docs, 1, 20, 42))

      renderWithProviders(<LibraryView />)

      await waitFor(() => {
        expect(screen.getByText('42 documents')).toBeInTheDocument()
      })
    })

    it('displays loading text while fetching count', () => {
      mockedGetDocuments.mockImplementation(() => new Promise(() => {}))

      renderWithProviders(<LibraryView />)

      expect(screen.getByText(/loading\.\.\./i)).toBeInTheDocument()
    })

    it('displays page title', async () => {
      const docs = createMockDocuments(3)
      mockedGetDocuments.mockResolvedValue(createMockResponse(docs))

      renderWithProviders(<LibraryView />)

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /document library/i })).toBeInTheDocument()
      })
    })
  })

  describe('Empty State Search', () => {
    it('shows search-specific message when query returns no results', async () => {
      mockedGetDocuments.mockResolvedValue(createMockResponse([]))

      renderWithProviders(<LibraryView />)

      await waitFor(() => {
        expect(screen.getByText(/no documents found/i)).toBeInTheDocument()
      })

      // Simulate having a search query
      const searchInput = screen.getByPlaceholderText(/search documents/i)
      fireEvent.change(searchInput, { target: { value: 'xyz' } })

      await waitFor(() => {
        expect(screen.getByText(/try adjusting your search terms/i)).toBeInTheDocument()
      })
    })
  })
})
