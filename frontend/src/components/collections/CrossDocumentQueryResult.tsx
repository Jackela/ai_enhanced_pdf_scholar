import React, { useState } from 'react'
import type { MultiDocumentQueryResponse } from '../../types'
import { Button } from '../ui/Button'

interface CrossDocumentQueryResultProps {
  queryResponse: MultiDocumentQueryResponse
}

const CrossDocumentQueryResult: React.FC<CrossDocumentQueryResultProps> = ({ 
  queryResponse 
}) => {
  const [activeTab, setActiveTab] = useState<'sources' | 'references'>('sources')
  const [expandedSources, setExpandedSources] = useState<Set<number>>(new Set())

  const toggleSourceExpansion = (index: number) => {
    const newExpanded = new Set(expandedSources)
    if (newExpanded.has(index)) {
      newExpanded.delete(index)
    } else {
      newExpanded.add(index)
    }
    setExpandedSources(newExpanded)
  }

  const formatConfidence = (confidence: number) => {
    return `${(confidence * 100).toFixed(1)}%`
  }

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-600 dark:text-green-400'
    if (confidence >= 0.6) return 'text-yellow-600 dark:text-yellow-400'
    return 'text-red-600 dark:text-red-400'
  }

  const formatProcessingTime = (timeMs: number) => {
    if (timeMs < 1000) return `${timeMs}ms`
    return `${(timeMs / 1000).toFixed(1)}s`
  }

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
      {/* Header with metadata */}
      <div className="bg-gray-50 dark:bg-gray-900 px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <h4 className="font-medium text-gray-900 dark:text-white">
            Query Results
          </h4>
          <div className="flex items-center space-x-4 text-sm text-gray-500 dark:text-gray-400">
            <span className={`font-medium ${getConfidenceColor(queryResponse.confidence)}`}>
              Confidence: {formatConfidence(queryResponse.confidence)}
            </span>
            <span>
              Time: {formatProcessingTime(queryResponse.processing_time_ms)}
            </span>
            {queryResponse.tokens_used && (
              <span>
                Tokens: {queryResponse.tokens_used}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700">
        <div className="flex">
          <button
            onClick={() => setActiveTab('sources')}
            className={`px-4 py-2 text-sm font-medium border-b-2 ${
              activeTab === 'sources'
                ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400'
            }`}
          >
            Sources ({queryResponse.sources.length})
          </button>
          <button
            onClick={() => setActiveTab('references')}
            className={`px-4 py-2 text-sm font-medium border-b-2 ${
              activeTab === 'references'
                ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400'
            }`}
          >
            Cross-References ({queryResponse.cross_references.length})
          </button>
        </div>
      </div>

      {/* Tab Content */}
      <div className="p-4">
        {activeTab === 'sources' && (
          <div className="space-y-4">
            {queryResponse.sources.length === 0 ? (
              <p className="text-gray-500 dark:text-gray-400 text-center py-4">
                No sources found for this query
              </p>
            ) : (
              queryResponse.sources.map((source, index) => (
                <div
                  key={index}
                  className="border border-gray-200 dark:border-gray-700 rounded-lg p-4"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2">
                        <span className="font-medium text-gray-900 dark:text-white">
                          Document #{source.document_id}
                        </span>
                        <span className={`text-sm font-medium ${getConfidenceColor(source.relevance_score)}`}>
                          {formatConfidence(source.relevance_score)} relevance
                        </span>
                        {source.page_number && (
                          <span className="text-sm text-gray-500 dark:text-gray-400">
                            Page {source.page_number}
                          </span>
                        )}
                      </div>
                      {source.chunk_id && (
                        <div className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                          Chunk: {source.chunk_id}
                        </div>
                      )}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => toggleSourceExpansion(index)}
                    >
                      {expandedSources.has(index) ? 'Collapse' : 'Expand'}
                    </Button>
                  </div>
                  
                  <div className={`text-gray-700 dark:text-gray-300 ${
                    expandedSources.has(index) ? '' : 'line-clamp-3'
                  }`}>
                    {source.excerpt}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'references' && (
          <div className="space-y-4">
            {queryResponse.cross_references.length === 0 ? (
              <p className="text-gray-500 dark:text-gray-400 text-center py-4">
                No cross-references found for this query
              </p>
            ) : (
              queryResponse.cross_references.map((reference, index) => (
                <div
                  key={index}
                  className="border border-gray-200 dark:border-gray-700 rounded-lg p-4"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center space-x-2">
                      <span className="font-medium text-gray-900 dark:text-white">
                        Doc #{reference.source_doc_id} → Doc #{reference.target_doc_id}
                      </span>
                      <span className="px-2 py-1 bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 text-xs rounded">
                        {reference.relation_type}
                      </span>
                      <span className={`text-sm font-medium ${getConfidenceColor(reference.confidence)}`}>
                        {formatConfidence(reference.confidence)}
                      </span>
                    </div>
                  </div>
                  
                  {reference.description && (
                    <p className="text-gray-700 dark:text-gray-300 text-sm">
                      {reference.description}
                    </p>
                  )}
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default CrossDocumentQueryResult