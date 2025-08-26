import React, { useState } from 'react'
import type { DocumentCollection } from '../../types'
import { Button } from '../ui/Button'

interface CollectionCardProps {
  collection: DocumentCollection
  onClick: () => void
  onDelete: () => void
}

const CollectionCard: React.FC<CollectionCardProps> = ({ 
  collection, 
  onClick, 
  onDelete 
}) => {
  const [isDeleting, setIsDeleting] = useState(false)

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (window.confirm(`Are you sure you want to delete "${collection.name}"?`)) {
      setIsDeleting(true)
      try {
        await onDelete()
      } finally {
        setIsDeleting(false)
      }
    }
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Unknown'
    return new Date(dateString).toLocaleDateString()
  }

  return (
    <div 
      className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6 hover:shadow-md transition-shadow cursor-pointer"
      onClick={onClick}
    >
      {/* Header */}
      <div className="flex justify-between items-start mb-4">
        <div className="flex-1">
          <h3 className="font-semibold text-lg text-gray-900 dark:text-white truncate">
            {collection.name}
          </h3>
          {collection.description && (
            <p className="text-gray-600 dark:text-gray-400 text-sm mt-1 line-clamp-2">
              {collection.description}
            </p>
          )}
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleDelete}
          disabled={isDeleting}
          className="ml-2 text-red-600 hover:text-red-700 hover:bg-red-50 dark:text-red-400"
        >
          {isDeleting ? '...' : '×'}
        </Button>
      </div>

      {/* Stats */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-600 dark:text-gray-400">Documents</span>
          <span className="font-medium text-gray-900 dark:text-white">
            {collection.document_count}
          </span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-600 dark:text-gray-400">Created</span>
          <span className="text-gray-900 dark:text-white">
            {formatDate(collection.created_at)}
          </span>
        </div>
        {collection.updated_at && collection.updated_at !== collection.created_at && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-600 dark:text-gray-400">Updated</span>
            <span className="text-gray-900 dark:text-white">
              {formatDate(collection.updated_at)}
            </span>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center text-sm text-gray-500 dark:text-gray-400">
          <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M4 4a2 2 0 00-2 2v8a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2H4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z" clipRule="evenodd" />
          </svg>
          Cross-document queries enabled
        </div>
      </div>
    </div>
  )
}

export default CollectionCard