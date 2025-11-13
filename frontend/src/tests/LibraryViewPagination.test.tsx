import type { ReactElement } from 'react'
import { describe, expect, it, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

import LibraryView from '../components/views/LibraryView'
import { api } from '../lib/api'
import type { DocumentListResponse } from '../types'

vi.mock('../lib/api', () => ({
  api: {
    getDocuments: vi.fn(),
  },
}))

const mockedGetDocuments = vi.mocked(api.getDocuments)

const sampleResponse: DocumentListResponse = {
  success: true,
  data: [
    {
      id: 1,
      title: 'Research Paper.pdf',
      file_path: '/tmp/research.pdf',
      file_hash: 'hash-1',
      file_size: 1048576,
      page_count: 12,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      last_accessed: null,
      metadata: null,
      is_file_available: true,
      content_hash: null,
      _links: {
        self: '/api/documents/1',
        related: {
          download: '/api/documents/1/download',
        },
      },
    },
  ],
  meta: {
    timestamp: new Date().toISOString(),
    version: 'v2',
    request_id: 'test',
    page: 2,
    per_page: 5,
    total: 12,
    total_pages: 3,
    has_next: true,
    has_prev: true,
  },
  errors: null,
}

function renderWithProviders(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('LibraryView pagination metadata', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedGetDocuments.mockResolvedValue(sampleResponse)
  })

  it('displays total documents and pagination text from the API envelope', async () => {
    renderWithProviders(<LibraryView />)

    await waitFor(() => {
      expect(screen.getByText('12 documents')).toBeInTheDocument()
    })

    expect(screen.getByText('Page 2 of 3')).toBeInTheDocument()
  })
})
