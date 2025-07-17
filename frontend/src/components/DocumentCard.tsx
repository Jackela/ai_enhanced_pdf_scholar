import { Link } from 'react-router-dom'
import { FileText, Calendar, HardDrive, Eye, MessageSquare, MoreVertical, Download, Trash2 } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { formatFileSize, formatDate } from '../lib/utils'
import { Button } from './ui/Button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from './ui/DropdownMenu'
import { useToast } from '../hooks/useToast'
import type { Document } from '../types'

interface DocumentCardProps {
  document: Document
  variant?: 'grid' | 'list'
}

export function DocumentCard({ document, variant = 'grid' }: DocumentCardProps) {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteDocument(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] })
      toast({
        title: 'Document deleted',
        description: `${document.title} has been removed from your library.`,
      })
    },
    onError: (error) => {
      toast({
        title: 'Failed to delete document',
        description: error instanceof Error ? error.message : 'An error occurred',
        variant: 'destructive',
      })
    },
  })

  const handleDownload = async () => {
    try {
      const blob = await api.downloadDocument(document.id)
      const url = window.URL.createObjectURL(blob)
      const link = window.document.createElement('a')
      link.href = url
      link.download = document.title
      window.document.body.appendChild(link)
      link.click()
      window.document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    } catch (error) {
      toast({
        title: 'Download failed',
        description: 'Could not download the document',
        variant: 'destructive',
      })
    }
  }

  const handleDelete = () => {
    if (window.confirm(`Are you sure you want to delete "${document.title}"?`)) {
      deleteMutation.mutate(document.id)
    }
  }

  if (variant === 'list') {
    return (
      <div className="flex items-center p-4 border rounded-lg hover:bg-accent transition-colors">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <div className={`p-2 rounded-lg ${document.is_file_available ? 'bg-primary/10 text-primary' : 'bg-red-100 text-red-600'}`}>
            <FileText className="h-5 w-5" />
          </div>
          
          <div className="flex-1 min-w-0">
            <Link 
              to={`/document/${document.id}`}
              className="font-medium hover:text-primary transition-colors block truncate"
            >
              {document.title}
            </Link>
            <div className="flex items-center gap-4 text-sm text-muted-foreground mt-1">
              <span className="flex items-center gap-1">
                <HardDrive className="h-3 w-3" />
                {formatFileSize(document.file_size)}
              </span>
              <span className="flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                {formatDate(document.updated_at)}
              </span>
              {document.page_count && (
                <span>{document.page_count} pages</span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" asChild>
            <Link to={`/document/${document.id}`}>
              <Eye className="h-4 w-4" />
            </Link>
          </Button>
          
          <Button variant="ghost" size="sm" asChild>
            <Link to={`/chat/${document.id}`}>
              <MessageSquare className="h-4 w-4" />
            </Link>
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={handleDownload}>
                <Download className="h-4 w-4 mr-2" />
                Download
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleDelete} className="text-red-600">
                <Trash2 className="h-4 w-4 mr-2" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    )
  }

  return (
    <div className="card hover:shadow-md transition-shadow">
      <div className="card-content p-4">
        <div className="flex items-start justify-between mb-3">
          <div className={`p-2 rounded-lg ${document.is_file_available ? 'bg-primary/10 text-primary' : 'bg-red-100 text-red-600'}`}>
            <FileText className="h-6 w-6" />
          </div>
          
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={handleDownload}>
                <Download className="h-4 w-4 mr-2" />
                Download
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleDelete} className="text-red-600">
                <Trash2 className="h-4 w-4 mr-2" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <div className="mb-4">
          <Link 
            to={`/document/${document.id}`}
            className="font-semibold hover:text-primary transition-colors block mb-2 line-clamp-2"
          >
            {document.title}
          </Link>
          
          <div className="space-y-1 text-sm text-muted-foreground">
            <div className="flex items-center gap-1">
              <HardDrive className="h-3 w-3" />
              <span>{formatFileSize(document.file_size)}</span>
              {document.page_count && (
                <>
                  <span className="mx-1">•</span>
                  <span>{document.page_count} pages</span>
                </>
              )}
            </div>
            
            <div className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              <span>Updated {formatDate(document.updated_at)}</span>
            </div>
          </div>
        </div>

        <div className="flex gap-2">
          <Button variant="outline" size="sm" className="flex-1" asChild>
            <Link to={`/document/${document.id}`}>
              <Eye className="h-4 w-4 mr-2" />
              View
            </Link>
          </Button>
          
          <Button variant="outline" size="sm" className="flex-1" asChild>
            <Link to={`/chat/${document.id}`}>
              <MessageSquare className="h-4 w-4 mr-2" />
              Chat
            </Link>
          </Button>
        </div>

        {!document.is_file_available && (
          <div className="mt-3 p-2 bg-red-50 text-red-700 text-xs rounded border border-red-200">
            File not found on disk
          </div>
        )}
      </div>
    </div>
  )
}