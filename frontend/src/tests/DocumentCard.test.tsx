import { describe, expect, it } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { DocumentCard } from '../components/DocumentCard'
import type { Document } from '../types'

const baseDocument: Document = {
  id: 1,
  title: 'Sample.pdf',
  file_path: '/tmp/sample.pdf',
  file_hash: 'hash',
  file_size: 12345,
  page_count: 3,
  preview_url: '/api/documents/1/preview',
  thumbnail_url: '/api/documents/1/thumbnail',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  last_accessed: null,
  metadata: null,
  is_file_available: true,
  content_hash: null,
  _links: {
    self: '/api/documents/1',
  },
}

function renderWithProviders(node: React.ReactNode) {
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{node}</MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('DocumentCard', () => {
  it('renders thumbnail when available', () => {
    renderWithProviders(<DocumentCard document={baseDocument} />)

    expect(screen.getByAltText('Thumbnail for Sample.pdf')).toBeInTheDocument()
  })

  it('renders preview button when preview url exists', () => {
    renderWithProviders(<DocumentCard document={baseDocument} variant='list' />)

    expect(screen.getAllByText(/Preview/i).length).toBeGreaterThan(0)
  })

  it('hides preview button when preview is unavailable', () => {
    const noPreviewDoc: Document = { ...baseDocument, preview_url: null, thumbnail_url: null }
    renderWithProviders(<DocumentCard document={noPreviewDoc} />)

    expect(screen.queryByText(/Preview/i)).toBeNull()
  })
})
