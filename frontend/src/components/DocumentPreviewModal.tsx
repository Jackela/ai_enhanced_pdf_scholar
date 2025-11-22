import { useEffect, useMemo, useRef, useState } from 'react'
import { X, ChevronLeft, ChevronRight } from 'lucide-react'

import type { Document } from '../types'
import { api } from '../lib/api'
import { useToast } from '../hooks/useToast'

interface DocumentPreviewModalProps {
  document: Document
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function DocumentPreviewModal({ document, open, onOpenChange }: DocumentPreviewModalProps) {
  const { toast } = useToast()
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState<'idle' | 'loading' | 'error' | 'success'>('idle')
  const [errorMessage, setErrorMessage] = useState<string | undefined>()
  const [imageSrc, setImageSrc] = useState<string | null>(null)
  const latestSrcRef = useRef<string | null>(null)

  const maxPage = useMemo(() => document.page_count ?? 1, [document.page_count])

  useEffect(() => {
    if (!open) {
      if (latestSrcRef.current) {
        URL.revokeObjectURL(latestSrcRef.current)
        latestSrcRef.current = null
      }
      setStatus('idle')
      setErrorMessage(undefined)
      setImageSrc(null)
      setPage(1)
      return
    }

    let cancelled = false
    const fetchPreview = async () => {
      if (!document.preview_url) {
        setStatus('error')
        setErrorMessage('Preview disabled by server')
        return
      }
      try {
        setStatus('loading')
        setErrorMessage(undefined)
        const blob = await api.fetchDocumentPreview(document.id, { page, width: 768 })
        if (cancelled) {
          URL.revokeObjectURL(URL.createObjectURL(blob))
          return
        }
        const nextSrc = URL.createObjectURL(blob)
        if (latestSrcRef.current) {
          URL.revokeObjectURL(latestSrcRef.current)
        }
        latestSrcRef.current = nextSrc
        setImageSrc(nextSrc)
        setStatus('success')
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to load preview'
        setStatus('error')
        setErrorMessage(message)
        setImageSrc(null)
        toast({
          title: 'Preview unavailable',
          description: message,
          variant: 'destructive',
        })
      }
    }

    fetchPreview()
    return () => {
      cancelled = true
    }
  }, [document.id, document.preview_url, open, page])

  if (!open) {
    return null
  }

  const close = () => onOpenChange(false)

  const disablePrev = page <= 1
  const disableNext = page >= maxPage
  const isLoading = status === 'loading'

  return (
    <div className='fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4'>
      <div className='relative w-full max-w-4xl rounded-lg bg-background shadow-2xl'>
        <button
          type='button'
          onClick={close}
          className='absolute right-4 top-4 rounded-full bg-black/60 p-1 text-white hover:bg-black/80'
          aria-label='Close preview'
        >
          <X className='h-5 w-5' />
        </button>

        <div className='flex flex-col gap-4 p-6'>
          <div className='flex items-center justify-between'>
            <div>
              <h2 className='text-lg font-semibold'>{document.title}</h2>
              <p className='text-sm text-muted-foreground'>
                Page {page} of {maxPage}
              </p>
            </div>

            <div className='flex items-center gap-2'>
              <button
                type='button'
                onClick={() => setPage(prev => Math.max(1, prev - 1))}
                disabled={disablePrev || isLoading}
                className='rounded border px-3 py-1 text-sm disabled:opacity-50'
              >
                <ChevronLeft className='mr-1 inline h-4 w-4' /> Prev
              </button>
              <button
                type='button'
                onClick={() => setPage(prev => prev + 1)}
                disabled={disableNext || isLoading}
                className='rounded border px-3 py-1 text-sm disabled:opacity-50'
              >
                Next <ChevronRight className='ml-1 inline h-4 w-4' />
              </button>
            </div>
          </div>

          <div className='flex min-h-[400px] items-center justify-center rounded border bg-muted/20'>
            {status === 'loading' && <p className='text-sm text-muted-foreground'>Loading preview…</p>}
            {status === 'error' && (
              <p className='text-sm text-destructive'>{errorMessage ?? 'Preview unavailable'}</p>
            )}
            {status === 'success' && imageSrc && (
              <img
                src={imageSrc}
                alt={`Preview of ${document.title} page ${page}`}
                className='max-h-[600px] w-auto rounded shadow-inner'
              />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
