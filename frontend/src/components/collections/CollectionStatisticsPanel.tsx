import React from 'react'
import type { CollectionStatistics } from '../../types'

interface CollectionStatisticsPanelProps {
  statistics: CollectionStatistics
}

const CollectionStatisticsPanel: React.FC<CollectionStatisticsPanelProps> = ({
  statistics
}) => {
  const formatFileSize = (sizeInBytes: number) => {
    const mbSize = sizeInBytes / (1024 * 1024)
    if (mbSize < 1) {
      return `${(sizeInBytes / 1024).toFixed(1)} KB`
    }
    return `${mbSize.toFixed(1)} MB`
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Unknown'
    return new Date(dateString).toLocaleDateString()
  }

  const formatTime = (timeMs?: number) => {
    if (!timeMs) return 'N/A'
    if (timeMs < 1000) return `${timeMs}ms`
    return `${(timeMs / 1000).toFixed(1)}s`
  }

  const StatCard: React.FC<{ title: string; value: string | number; subtitle?: string }> = ({
    title,
    value,
    subtitle
  }) => (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
      <h3 className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">
        {title}
      </h3>
      <div className="text-2xl font-bold text-gray-900 dark:text-white">
        {value}
      </div>
      {subtitle && (
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          {subtitle}
        </p>
      )}
    </div>
  )

  return (
    <div className="space-y-6">
      {/* Overview Stats */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Collection Overview
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard
            title="Total Documents"
            value={statistics.document_count}
          />
          <StatCard
            title="Total File Size"
            value={formatFileSize(statistics.total_file_size)}
          />
          <StatCard
            title="Average File Size"
            value={formatFileSize(statistics.avg_file_size)}
          />
          <StatCard
            title="Created"
            value={formatDate(statistics.created_at)}
          />
        </div>
      </div>

      {/* Query Statistics */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Query Performance
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <StatCard
            title="Recent Queries"
            value={statistics.recent_queries}
            subtitle="Last 7 days"
          />
          <StatCard
            title="Average Query Time"
            value={formatTime(statistics.avg_query_time_ms)}
            subtitle="Processing time"
          />
        </div>
      </div>

      {/* Collection Health */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Collection Health
        </h2>
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-gray-600 dark:text-gray-400">
                Collection Status
              </span>
              <span className="px-3 py-1 bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200 rounded-full text-sm">
                Active
              </span>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-gray-600 dark:text-gray-400">
                Document Coverage
              </span>
              <span className="text-gray-900 dark:text-white font-medium">
                {statistics.document_count > 0 ? '100%' : '0%'}
              </span>
            </div>
            
            {statistics.recent_queries > 0 && (
              <div className="flex items-center justify-between">
                <span className="text-gray-600 dark:text-gray-400">
                  Query Activity
                </span>
                <span className="text-gray-900 dark:text-white font-medium">
                  {statistics.recent_queries > 10 ? 'High' : 
                   statistics.recent_queries > 5 ? 'Medium' : 'Low'}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Performance Insights */}
      {statistics.avg_query_time_ms && (
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Performance Insights
          </h2>
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
            <div className="space-y-3">
              {statistics.avg_query_time_ms < 2000 && (
                <div className="flex items-start space-x-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full mt-2"></div>
                  <div>
                    <p className="text-green-800 dark:text-green-200 font-medium">
                      Fast Query Performance
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Queries are processing efficiently in under 2 seconds
                    </p>
                  </div>
                </div>
              )}
              
              {statistics.avg_query_time_ms > 5000 && (
                <div className="flex items-start space-x-2">
                  <div className="w-2 h-2 bg-yellow-500 rounded-full mt-2"></div>
                  <div>
                    <p className="text-yellow-800 dark:text-yellow-200 font-medium">
                      Consider Index Optimization
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Query times are above 5 seconds. Rebuilding the index might help.
                    </p>
                  </div>
                </div>
              )}
              
              {statistics.document_count > 20 && (
                <div className="flex items-start space-x-2">
                  <div className="w-2 h-2 bg-blue-500 rounded-full mt-2"></div>
                  <div>
                    <p className="text-blue-800 dark:text-blue-200 font-medium">
                      Large Collection
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      This collection contains many documents. Consider organizing into smaller collections for better performance.
                    </p>
                  </div>
                </div>
              )}
              
              {statistics.recent_queries === 0 && (
                <div className="flex items-start space-x-2">
                  <div className="w-2 h-2 bg-gray-400 rounded-full mt-2"></div>
                  <div>
                    <p className="text-gray-600 dark:text-gray-400 font-medium">
                      No Recent Activity
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Start querying this collection to see performance metrics
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default CollectionStatisticsPanel