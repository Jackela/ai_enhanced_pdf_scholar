import React, { useState, useEffect } from 'react'
import { api } from '../../lib/api'
import { useToast } from '../../hooks/useToast'
import type { DocumentCollection, Document, CreateCollectionRequest } from '../../types'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'

interface CreateCollectionModalProps {
  isOpen: boolean
  onClose: () => void
  onCreate: (collection: DocumentCollection) => void
}

const CreateCollectionModal: React.FC<CreateCollectionModalProps> = ({
  isOpen,
  onClose,
  onCreate,
}) => {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [selectedDocuments, setSelectedDocuments] = useState<number[]>([])
  const [availableDocuments, setAvailableDocuments] = useState<Document[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingDocuments, setIsLoadingDocuments] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const { toast } = useToast()

  // Load available documents when modal opens
  useEffect(() => {
    if (isOpen) {
      fetchAvailableDocuments()
    }
  }, [isOpen])

  // Reset form when modal closes
  useEffect(() => {
    if (!isOpen) {
      setName('')
      setDescription('')
      setSelectedDocuments([])
      setSearchQuery('')
    }
  }, [isOpen])

  const fetchAvailableDocuments = async () => {
    try {
      setIsLoadingDocuments(true)
      const response = await api.getDocuments({ per_page: 100 })
      setAvailableDocuments(response.data ?? [])
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to load documents',
        variant: 'destructive',
      })
    } finally {
      setIsLoadingDocuments(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!name.trim()) {
      toast({
        title: 'Error',
        description: 'Collection name is required',
        variant: 'destructive',
      })
      return
    }

    if (selectedDocuments.length === 0) {
      toast({
        title: 'Error',
        description: 'At least one document must be selected',
        variant: 'destructive',
      })
      return
    }

    try {
      setIsLoading(true)
      const request: CreateCollectionRequest = {
        name: name.trim(),
        description: description.trim() || undefined,
        document_ids: selectedDocuments,
      }

      const collection = await api.createCollection(request)
      onCreate(collection)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create collection'
      toast({
        title: 'Error',
        description: errorMessage,
        variant: 'destructive',
      })
    } finally {
      setIsLoading(false)
    }
  }

  const toggleDocument = (documentId: number) => {
    setSelectedDocuments(prev =>
      prev.includes(documentId)
        ? prev.filter(id => id !== documentId)
        : [...prev, documentId]
    )
  }

  const filteredDocuments = availableDocuments.filter(doc =>
    searchQuery === '' ||
    doc.title.toLowerCase().includes(searchQuery.toLowerCase())
  )

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-hidden">
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            Create New Collection
          </h2>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6 overflow-y-auto max-h-[calc(90vh-140px)]">
          {/* Basic Information */}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Collection Name *
              </label>
              <Input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter collection name..."
                required
                maxLength={255}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Description (optional)
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe this collection..."
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
                rows={3}
                maxLength={1000}
              />
            </div>
          </div>

          {/* Document Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Select Documents * ({selectedDocuments.length} selected)
            </label>

            {/* Search Documents */}
            <div className="mb-4">
              <Input
                type="text"
                placeholder="Search documents..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            {/* Documents List */}
            <div className="border border-gray-300 dark:border-gray-600 rounded-md max-h-64 overflow-y-auto">
              {isLoadingDocuments ? (
                <div className="p-4 text-center text-gray-500">
                  Loading documents...
                </div>
              ) : filteredDocuments.length === 0 ? (
                <div className="p-4 text-center text-gray-500">
                  {searchQuery ? 'No documents match your search' : 'No documents available'}
                </div>
              ) : (
                <div className="divide-y divide-gray-200 dark:divide-gray-700">
                  {filteredDocuments.map((document) => (
                    <label
                      key={document.id}
                      className="flex items-center p-3 hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={selectedDocuments.includes(document.id)}
                        onChange={() => toggleDocument(document.id)}
                        className="mr-3 rounded border-gray-300 focus:ring-blue-500"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-gray-900 dark:text-white truncate">
                          {document.title}
                        </div>
                        <div className="text-sm text-gray-500 dark:text-gray-400">
                          {document.file_size ? `${(document.file_size / 1024 / 1024).toFixed(1)} MB` : 'Unknown size'}
                          {document.page_count && ` • ${document.page_count} pages`}
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
              )}
            </div>
          </div>
        </form>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 dark:border-gray-700 flex justify-end space-x-3">
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={isLoading}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            onClick={handleSubmit}
            disabled={isLoading || selectedDocuments.length === 0 || !name.trim()}
          >
            {isLoading ? 'Creating...' : 'Create Collection'}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default CreateCollectionModal
