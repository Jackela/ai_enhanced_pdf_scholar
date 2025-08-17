import React, { useState, useEffect } from 'react'
import { api } from '../../lib/api'
import { useToast } from '../../hooks/useToast'
import type { DocumentCollection, Document } from '../../types'
import CreateCollectionModal from '../collections/CreateCollectionModal'
import CollectionCard from '../collections/CollectionCard'
import CollectionViewer from '../collections/CollectionViewer'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'

interface CollectionsViewProps {
  onSelectDocument?: (document: Document) => void
}

const CollectionsView: React.FC<CollectionsViewProps> = ({ onSelectDocument }) => {
  const [collections, setCollections] = useState<DocumentCollection[]>([])
  const [selectedCollection, setSelectedCollection] = useState<DocumentCollection | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const { toast } = useToast()

  const fetchCollections = async (page: number = 1) => {
    try {
      setIsLoading(true)
      const response = await api.getCollections(page, 20)
      setCollections(response.collections)
      setTotalCount(response.total_count)
      setCurrentPage(page)
      setError(null)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch collections'
      setError(errorMessage)
      toast({
        title: 'Error',
        description: errorMessage,
        variant: 'destructive',
      })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchCollections()
  }, [])

  const handleCreateCollection = async (collection: DocumentCollection) => {
    setCollections(prev => [collection, ...prev])
    setIsCreateModalOpen(false)
    toast({
      title: 'Success',
      description: `Collection "${collection.name}" created successfully`,
    })
  }

  const handleDeleteCollection = async (id: number) => {
    try {
      await api.deleteCollection(id)
      setCollections(prev => prev.filter(c => c.id !== id))
      if (selectedCollection?.id === id) {
        setSelectedCollection(null)
      }
      toast({
        title: 'Success',
        description: 'Collection deleted successfully',
      })
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete collection'
      toast({
        title: 'Error',
        description: errorMessage,
        variant: 'destructive',
      })
    }
  }

  const handleUpdateCollection = async (id: number, updatedCollection: DocumentCollection) => {
    setCollections(prev => prev.map(c => c.id === id ? updatedCollection : c))
    if (selectedCollection?.id === id) {
      setSelectedCollection(updatedCollection)
    }
  }

  const filteredCollections = collections.filter(collection =>
    searchQuery === '' || 
    collection.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    collection.description?.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const totalPages = Math.ceil(totalCount / 20)

  if (selectedCollection) {
    return (
      <CollectionViewer
        collection={selectedCollection}
        onBack={() => setSelectedCollection(null)}
        onUpdate={(updated) => handleUpdateCollection(selectedCollection.id, updated)}
        onDelete={() => handleDeleteCollection(selectedCollection.id)}
        onSelectDocument={onSelectDocument}
      />
    )
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Document Collections
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Organize documents into collections for cross-document analysis
          </p>
        </div>
        <Button onClick={() => setIsCreateModalOpen(true)}>
          Create Collection
        </Button>
      </div>

      {/* Search and Filters */}
      <div className="flex gap-4">
        <div className="flex-1">
          <Input
            type="text"
            placeholder="Search collections..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full"
          />
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <p className="text-red-800 dark:text-red-200">{error}</p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchCollections()}
            className="mt-2"
          >
            Retry
          </Button>
        </div>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      )}

      {/* Collections Grid */}
      {!isLoading && !error && (
        <>
          {filteredCollections.length === 0 ? (
            <div className="text-center py-12">
              <div className="text-gray-400 text-lg mb-4">
                {searchQuery ? 'No collections match your search' : 'No collections yet'}
              </div>
              {!searchQuery && (
                <Button onClick={() => setIsCreateModalOpen(true)}>
                  Create Your First Collection
                </Button>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredCollections.map((collection) => (
                <CollectionCard
                  key={collection.id}
                  collection={collection}
                  onClick={() => setSelectedCollection(collection)}
                  onDelete={() => handleDeleteCollection(collection.id)}
                />
              ))}
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex justify-center items-center space-x-2 mt-8">
              <Button
                variant="outline"
                size="sm"
                onClick={() => fetchCollections(currentPage - 1)}
                disabled={currentPage === 1}
              >
                Previous
              </Button>
              <span className="text-sm text-gray-600 dark:text-gray-400">
                Page {currentPage} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => fetchCollections(currentPage + 1)}
                disabled={currentPage === totalPages}
              >
                Next
              </Button>
            </div>
          )}
        </>
      )}

      {/* Create Collection Modal */}
      <CreateCollectionModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onCreate={handleCreateCollection}
      />
    </div>
  )
}

export default CollectionsView