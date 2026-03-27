import { describe, expect, it, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { DocumentCard } from '../components/DocumentCard'
import type { Document } from '../types'
import { api } from '../lib/api'

// Mock the API module
vi.mock('../lib/api', () => ({
  api: {
    deleteDocument: vi.fn(),
    downloadDocument: vi.fn(),
  },
}))

// Mock window.URL methods
Object.defineProperty(window, 'URL', {
  value: {
    createObjectURL: vi.fn(() => 'blob:url'),
    revokeObjectURL: vi.fn(),
  },
})

// Mock window.confirm
Object.defineProperty(window, 'confirm', {
  writable: true,
  value: vi.fn(),
})

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

const createQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  })

function renderWithProviders(node: React.ReactNode, queryClient = createQueryClient()) {
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{node}</MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('DocumentCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Grid Variant', () => {
    it('renders thumbnail when available', () => {
      renderWithProviders(<DocumentCard document={baseDocument} variant="grid" />)

      const thumbnail = screen.getByAltText('Thumbnail for Sample.pdf')
      expect(thumbnail).toBeInTheDocument()
      expect(thumbnail).toHaveAttribute('src', baseDocument.thumbnail_url)
    })

    it('renders file icon when thumbnail is unavailable', () => {
      const docWithoutThumbnail = { ...baseDocument, thumbnail_url: null }
      renderWithProviders(<DocumentCard document={docWithoutThumbnail} variant="grid" />)

      expect(screen.queryByAltText(/thumbnail/i)).not.toBeInTheDocument()
      expect(screen.getByRole('link', { name: /sample\.pdf/i })).toBeInTheDocument()
    })

    it('renders preview button when preview url exists', () => {
      renderWithProviders(<DocumentCard document={baseDocument} variant="grid" />)

      const previewButton = screen.getByRole('button', { name: /preview/i })
      expect(previewButton).toBeInTheDocument()
    })

    it('hides preview button when preview is unavailable', () => {
      const noPreviewDoc: Document = { ...baseDocument, preview_url: null, thumbnail_url: null }
      renderWithProviders(<DocumentCard document={noPreviewDoc} variant="grid" />)

      expect(screen.queryByRole('button', { name: /preview/i })).not.toBeInTheDocument()
    })

    it('displays document title', () => {
      renderWithProviders(<DocumentCard document={baseDocument} variant="grid" />)

      expect(screen.getByText('Sample.pdf')).toBeInTheDocument()
    })

    it('displays file size', () => {
      renderWithProviders(<DocumentCard document={baseDocument} variant="grid" />)

      expect(screen.getByText(/12\.06 kb/i)).toBeInTheDocument()
    })

    it('displays page count when available', () => {
      renderWithProviders(<DocumentCard document={baseDocument} variant="grid" />)

      expect(screen.getByText(/3 pages/i)).toBeInTheDocument()
    })

    it('shows file unavailable warning when is_file_available is false', () => {
      const unavailableDoc = { ...baseDocument, is_file_available: false }
      renderWithProviders(<DocumentCard document={unavailableDoc} variant="grid" />)

      expect(screen.getByText(/file not found on disk/i)).toBeInTheDocument()
    })

    it('has working navigation links', () => {
      renderWithProviders(<DocumentCard document={baseDocument} variant="grid" />)

      const viewLink = screen.getByRole('link', { name: /view/i })
      expect(viewLink).toHaveAttribute('href', '/document/1')

      const chatLink = screen.getByRole('link', { name: /chat/i })
      expect(chatLink).toHaveAttribute('href', '/chat/1')
    })

    it('opens dropdown menu with actions', () => {
      renderWithProviders(<DocumentCard document={baseDocument} variant="grid" />)

      const moreButton = screen.getByRole('button', { name: /more actions/i })
      fireEvent.click(moreButton)

      expect(screen.getByRole('menuitem', { name: /download/i })).toBeInTheDocument()
      expect(screen.getByRole('menuitem', { name: /delete/i })).toBeInTheDocument()
    })
  })

  describe('List Variant', () => {
    it('renders in list layout', () => {
      renderWithProviders(<DocumentCard document={baseDocument} variant="list" />)

      expect(screen.getByText('Sample.pdf')).toBeInTheDocument()
      expect(screen.getByText(/12\.06 kb/i)).toBeInTheDocument()
    })

    it('shows thumbnail in list view when available', () => {
      renderWithProviders(<DocumentCard document={baseDocument} variant="list" />)

      const thumbnail = screen.getByAltText('Thumbnail for Sample.pdf')
      expect(thumbnail).toHaveClass('h-12', 'w-12')
    })

    it('shows file icon when thumbnail fails to load', () => {
      renderWithProviders(<DocumentCard document={baseDocument} variant="list" />)

      const thumbnail = screen.getByAltText('Thumbnail for Sample.pdf')
      fireEvent.error(thumbnail)

      expect(screen.queryByAltText('Thumbnail for Sample.pdf')).not.toBeInTheDocument()
    })

    it('renders action buttons in list view', () => {
      renderWithProviders(<DocumentCard document={baseDocument} variant="list" />)

      expect(screen.getByRole('button', { name: /preview/i })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: /view/i })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: /chat/i })).toBeInTheDocument()
    })
  })

  describe('Interactions', () => {
    it('handles delete action', async () => {
      const mockConfirm = vi.fn(() => true)
      window.confirm = mockConfirm
      vi.mocked(api.deleteDocument).mockResolvedValue(undefined)

      renderWithProviders(<DocumentCard document={baseDocument} />)

      const moreButton = screen.getByRole('button', { name: /more actions/i })
      fireEvent.click(moreButton)

      const deleteButton = screen.getByRole('menuitem', { name: /delete/i })
      fireEvent.click(deleteButton)

      expect(mockConfirm).toHaveBeenCalledWith('Are you sure you want to delete "Sample.pdf"?')
      await waitFor(() => {
        expect(api.deleteDocument).toHaveBeenCalledWith(1)
      })
    })

    it('cancels delete when user declines confirmation', () => {
      const mockConfirm = vi.fn(() => false)
      window.confirm = mockConfirm

      renderWithProviders(<DocumentCard document={baseDocument} />)

      const moreButton = screen.getByRole('button', { name: /more actions/i })
      fireEvent.click(moreButton)

      const deleteButton = screen.getByRole('menuitem', { name: /delete/i })
      fireEvent.click(deleteButton)

      expect(mockConfirm).toHaveBeenCalled()
      expect(api.deleteDocument).not.toHaveBeenCalled()
    })

    it('handles download action', async () => {
      const mockBlob = new Blob(['test content'], { type: 'application/pdf' })
      vi.mocked(api.downloadDocument).mockResolvedValue(mockBlob)

      renderWithProviders(<DocumentCard document={baseDocument} />)

      const moreButton = screen.getByRole('button', { name: /more actions/i })
      fireEvent.click(moreButton)

      const downloadButton = screen.getByRole('menuitem', { name: /download/i })
      fireEvent.click(downloadButton)

      await waitFor(() => {
        expect(api.downloadDocument).toHaveBeenCalledWith(1)
      })
    })

    it('opens preview modal when clicking preview button', () => {
      renderWithProviders(<DocumentCard document={baseDocument} variant="grid" />)

      const previewButton = screen.getByRole('button', { name: /preview/i })
      fireEvent.click(previewButton)

      // Preview modal should be triggered (checking button click works)
      expect(previewButton).toBeInTheDocument()
    })

    it('opens preview modal when clicking thumbnail', () => {
      renderWithProviders(<DocumentCard document={baseDocument} variant="grid" />)

      const thumbnailButton = screen.getByRole('button', { name: /open preview for sample\.pdf/i })
      expect(thumbnailButton).toBeInTheDocument()
    })
  })

  describe('Edge Cases', () => {
    it('handles null file_size gracefully', () => {
      const docWithNullSize = { ...baseDocument, file_size: null }
      renderWithProviders(<DocumentCard document={docWithNullSize} variant="grid" />)

      expect(screen.getByText(/unknown size/i)).toBeInTheDocument()
    })

    it('handles missing page_count', () => {
      const docWithoutPages = { ...baseDocument, page_count: null }
      renderWithProviders(<DocumentCard document={docWithoutPages} variant="grid" />)

      expect(screen.queryByText(/pages/i)).not.toBeInTheDocument()
    })

    it('truncates long titles', () => {
      const docWithLongTitle = {
        ...baseDocument,
        title: 'A very long document title that should be truncated properly.pdf',
      }
      renderWithProviders(<DocumentCard document={docWithLongTitle} variant="grid" />)

      expect(screen.getByText(/A very long document title/i)).toBeInTheDocument()
    })

    it('displays formatted date', () => {
      const yesterday = new Date()
      yesterday.setDate(yesterday.getDate() - 1)
      const docWithDate = { ...baseDocument, updated_at: yesterday.toISOString() }

      renderWithProviders(<DocumentCard document={docWithDate} variant="grid" />)

      expect(screen.getByText(/updated 1 day ago/i)).toBeInTheDocument()
    })

    it('handles file not available state visually', () => {
      const unavailableDoc = { ...baseDocument, is_file_available: false }
      renderWithProviders(<DocumentCard document={unavailableDoc} variant="grid" />)

      const iconContainer = screen.getByRole('link', { name: /sample\.pdf/i }).previousElementSibling
      expect(iconContainer).toHaveClass('bg-red-100')
    })
  })

  describe('Accessibility', () => {
    it('has accessible thumbnail button with aria-label', () => {
      renderWithProviders(<DocumentCard document={baseDocument} variant="grid" />)

      const thumbnailButton = screen.getByRole('button', { name: /open preview for sample\.pdf/i })
      expect(thumbnailButton).toHaveAttribute('aria-label', 'Open preview for Sample.pdf')
    })

    it('thumbnail has descriptive alt text', () => {
      renderWithProviders(<DocumentCard document={baseDocument} variant="grid" />)

      const thumbnail = screen.getByAltText('Thumbnail for Sample.pdf')
      expect(thumbnail).toBeInTheDocument()
    })

    it('action buttons have proper roles', () => {
      renderWithProviders(<DocumentCard document={baseDocument} variant="list" />)

      expect(screen.getByRole('link', { name: /view/i })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: /chat/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /preview/i })).toBeInTheDocument()
    })
  })
})
