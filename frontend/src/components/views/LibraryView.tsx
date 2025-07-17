import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Plus, Search, Filter, Grid, List, Upload } from 'lucide-react'
import { api } from '../../lib/api'
import { DocumentCard } from '../DocumentCard'
import { DocumentUpload } from '../DocumentUpload'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import type { SearchFilters, Document } from '../../types'

export function LibraryView() {
  const [searchFilters, setSearchFilters] = useState<SearchFilters>({
    page: 1,
    per_page: 20,
    sort_by: 'updated_at',
    sort_order: 'desc',
  })
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [showUpload, setShowUpload] = useState(false)

  const { data: documents, isLoading, error, refetch } = useQuery({
    queryKey: ['documents', searchFilters],
    queryFn: () => api.getDocuments(searchFilters),
  })

  const handleSearch = (query: string) => {
    setSearchFilters(prev => ({
      ...prev,
      query: query || undefined,
      page: 1,
    }))
  }

  // const handleSortChange = (sortBy: string) => {
  //   setSearchFilters(prev => ({
  //     ...prev,
  //     sort_by: sortBy as any,
  //     sort_order: prev.sort_by === sortBy && prev.sort_order === 'desc' ? 'asc' : 'desc',
  //     page: 1,
  //   }))
  // }

  const handlePageChange = (page: number) => {
    setSearchFilters(prev => ({ ...prev, page }))
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <p className="text-red-600 mb-4">Failed to load documents</p>
          <Button onClick={() => refetch()}>Try Again</Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 sticky top-0 z-40">
        <div className="flex items-center justify-between p-6">
          <div>
            <h1 className="text-2xl font-semibold">Document Library</h1>
            <p className="text-muted-foreground">
              {documents ? `${documents.total} documents` : 'Loading...'}
            </p>
          </div>
          
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setViewMode(viewMode === 'grid' ? 'list' : 'grid')}
            >
              {viewMode === 'grid' ? <List className="h-4 w-4" /> : <Grid className="h-4 w-4" />}
            </Button>
            
            <Button onClick={() => setShowUpload(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Add Document
            </Button>
          </div>
        </div>

        {/* Search and Filters */}
        <div className="px-6 pb-4">
          <div className="flex items-center gap-4">
            <div className="flex-1 max-w-md">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
                <Input
                  placeholder="Search documents..."
                  className="pl-10"
                  onChange={(e) => handleSearch(e.target.value)}
                />
              </div>
            </div>

            <Button variant="outline" size="sm">
              <Filter className="h-4 w-4 mr-2" />
              Filters
            </Button>

            <select
              className="px-3 py-2 text-sm border border-input rounded-md bg-background"
              value={`${searchFilters.sort_by}_${searchFilters.sort_order}`}
              onChange={(e) => {
                const [sortBy, sortOrder] = e.target.value.split('_')
                setSearchFilters(prev => ({
                  ...prev,
                  sort_by: sortBy as any,
                  sort_order: sortOrder as any,
                  page: 1,
                }))
              }}
            >
              <option value="updated_at_desc">Recently Updated</option>
              <option value="created_at_desc">Recently Added</option>
              <option value="title_asc">Title A-Z</option>
              <option value="title_desc">Title Z-A</option>
              <option value="file_size_desc">Largest Files</option>
              <option value="file_size_asc">Smallest Files</option>
            </select>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full" />
          </div>
        ) : documents?.documents.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Upload className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No documents found</h3>
            <p className="text-muted-foreground mb-4">
              {searchFilters.query ? 'Try adjusting your search terms' : 'Start by uploading your first document'}
            </p>
            <Button onClick={() => setShowUpload(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Upload Document
            </Button>
          </div>
        ) : (
          <div className="p-6">
            {viewMode === 'grid' ? (
              <div className="document-grid">
                {documents?.documents.map((document: Document) => (
                  <DocumentCard key={document.id} document={document} />
                ))}
              </div>
            ) : (
              <div className="space-y-2">
                {documents?.documents.map((document: Document) => (
                  <DocumentCard key={document.id} document={document} variant="list" />
                ))}
              </div>
            )}

            {/* Pagination */}
            {documents && documents.total > documents.per_page && (
              <div className="flex items-center justify-center mt-8 gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={documents.page <= 1}
                  onClick={() => handlePageChange(documents.page - 1)}
                >
                  Previous
                </Button>
                
                <span className="text-sm text-muted-foreground">
                  Page {documents.page} of {Math.ceil(documents.total / documents.per_page)}
                </span>
                
                <Button
                  variant="outline"
                  size="sm"
                  disabled={documents.page >= Math.ceil(documents.total / documents.per_page)}
                  onClick={() => handlePageChange(documents.page + 1)}
                >
                  Next
                </Button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Upload Modal */}
      {showUpload && (
        <DocumentUpload
          onClose={() => setShowUpload(false)}
          onSuccess={() => {
            setShowUpload(false)
            refetch()
          }}
        />
      )}
    </div>
  )
}