import React, { useState, useEffect } from 'react'
import { api } from '../../lib/api'
import { useToast } from '../../hooks/useToast'
import type { 
  DocumentCollection, 
  Document, 
  CollectionStatistics 
} from '../../types'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import CrossDocumentChat from './CrossDocumentChat'
import CollectionStatisticsPanel from './CollectionStatisticsPanel'

interface CollectionViewerProps {
  collection: DocumentCollection
  onBack: () => void
  onUpdate: (collection: DocumentCollection) => void
  onDelete: () => void
  onSelectDocument?: (document: Document) => void
}

const CollectionViewer: React.FC<CollectionViewerProps> = ({
  collection,
  onBack,
  onUpdate,
  onDelete,
  onSelectDocument,
}) => {
  const [documents, setDocuments] = useState<Document[]>([])
  const [statistics, setStatistics] = useState<CollectionStatistics | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isEditing, setIsEditing] = useState(false)
  const [editName, setEditName] = useState(collection.name)
  const [editDescription, setEditDescription] = useState(collection.description || '')
  const [activeTab, setActiveTab] = useState<'overview' | 'documents' | 'query' | 'statistics'>('overview')
  const [isCreatingIndex, setIsCreatingIndex] = useState(false)
  const { toast } = useToast()

  useEffect(() => {
    loadCollectionDetails()
  }, [collection.id])

  const loadCollectionDetails = async () => {
    try {
      setIsLoading(true)
      
      // Load documents
      const documentPromises = collection.document_ids.map(id => api.getDocument(id))
      const documentResults = await Promise.allSettled(documentPromises)
      
      const loadedDocuments = documentResults
        .filter((result): result is PromiseFulfilledResult<Document> => result.status === 'fulfilled')
        .map(result => result.value)
      
      setDocuments(loadedDocuments)

      // Load statistics
      try {
        const stats = await api.getCollectionStatistics(collection.id)
        setStatistics(stats)
      } catch (err) {
        console.warn('Statistics not available:', err)
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to load collection details',
        variant: 'destructive',
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleSaveEdit = async () => {
    try {
      const updatedCollection = await api.updateCollection(collection.id, {
        name: editName.trim(),
        description: editDescription.trim() || undefined,
      })
      onUpdate(updatedCollection)
      setIsEditing(false)
      toast({
        title: 'Success',
        description: 'Collection updated successfully',
      })
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to update collection',
        variant: 'destructive',
      })
    }
  }

  const handleCreateIndex = async () => {
    try {
      setIsCreatingIndex(true)
      await api.createCollectionIndex(collection.id)
      toast({
        title: 'Success',
        description: 'Index creation started. This may take a few minutes.',
      })
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to start index creation',
        variant: 'destructive',
      })
    } finally {
      setIsCreatingIndex(false)
    }
  }

  const handleRemoveDocument = async (documentId: number) => {
    try {
      const updatedCollection = await api.removeDocumentFromCollection(collection.id, documentId)
      onUpdate(updatedCollection)
      setDocuments(prev => prev.filter(d => d.id !== documentId))
      toast({
        title: 'Success',
        description: 'Document removed from collection',
      })
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to remove document',
        variant: 'destructive',
      })
    }
  }

  const handleDeleteCollection = () => {
    if (window.confirm(`Are you sure you want to delete "${collection.name}"? This action cannot be undone.`)) {
      onDelete()
      onBack()
    }
  }

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'documents', label: `Documents (${documents.length})` },
    { id: 'query', label: 'Cross-Document Query' },
    { id: 'statistics', label: 'Statistics' },
  ]

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Button variant="outline" onClick={onBack}>
            ← Back
          </Button>
          <div>
            {isEditing ? (
              <div className="space-y-2">
                <Input
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="text-xl font-bold"
                />
                <textarea
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  placeholder="Collection description..."
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
                  rows={2}
                />
                <div className="flex space-x-2">
                  <Button size="sm" onClick={handleSaveEdit}>
                    Save
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setIsEditing(false)
                      setEditName(collection.name)
                      setEditDescription(collection.description || '')
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                  {collection.name}
                </h1>
                {collection.description && (
                  <p className="text-gray-600 dark:text-gray-400 mt-1">
                    {collection.description}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
        
        <div className="flex space-x-2">
          {!isEditing && (
            <Button variant="outline" onClick={() => setIsEditing(true)}>
              Edit
            </Button>
          )}
          <Button
            variant="outline"
            onClick={handleCreateIndex}
            disabled={isCreatingIndex}
          >
            {isCreatingIndex ? 'Creating Index...' : 'Rebuild Index'}
          </Button>
          <Button variant="outline" onClick={handleDeleteCollection}>
            Delete
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700">
        <div className="flex space-x-8">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      ) : (
        <>
          {activeTab === 'overview' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
                  <h3 className="font-medium text-gray-900 dark:text-white">Documents</h3>
                  <p className="text-2xl font-bold text-blue-600 mt-2">{collection.document_count}</p>
                </div>
                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
                  <h3 className="font-medium text-gray-900 dark:text-white">Created</h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
                    {collection.created_at ? new Date(collection.created_at).toLocaleDateString() : 'Unknown'}
                  </p>
                </div>
                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
                  <h3 className="font-medium text-gray-900 dark:text-white">Last Updated</h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
                    {collection.updated_at ? new Date(collection.updated_at).toLocaleDateString() : 'Never'}
                  </p>
                </div>
              </div>
              
              <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
                <h3 className="font-medium text-gray-900 dark:text-white mb-4">Quick Actions</h3>
                <div className="flex space-x-4">
                  <Button onClick={() => setActiveTab('query')}>
                    Start Cross-Document Query
                  </Button>
                  <Button variant="outline" onClick={() => setActiveTab('documents')}>
                    Manage Documents
                  </Button>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'documents' && (
            <div className="space-y-4">
              {documents.length === 0 ? (
                <div className="text-center py-12">
                  <p className="text-gray-500">No documents in this collection</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {documents.map((document) => (
                    <div
                      key={document.id}
                      className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 flex items-center justify-between"
                    >
                      <div className="flex-1">
                        <h4 className="font-medium text-gray-900 dark:text-white">
                          {document.title}
                        </h4>
                        <div className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                          {document.file_size ? `${(document.file_size / 1024 / 1024).toFixed(1)} MB` : 'Unknown size'}
                          {document.page_count && ` • ${document.page_count} pages`}
                        </div>
                      </div>
                      <div className="flex space-x-2">
                        {onSelectDocument && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => onSelectDocument(document)}
                          >
                            View
                          </Button>
                        )}
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleRemoveDocument(document.id)}
                        >
                          Remove
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'query' && (
            <CrossDocumentChat collection={collection} />
          )}

          {activeTab === 'statistics' && statistics && (
            <CollectionStatisticsPanel statistics={statistics} />
          )}
        </>
      )}
    </div>
  )
}

export default CollectionViewer