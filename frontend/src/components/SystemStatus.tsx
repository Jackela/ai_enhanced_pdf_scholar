// React import removed
import { useQuery } from '@tanstack/react-query'
import { Activity, Database, Wifi, AlertTriangle, CheckCircle } from 'lucide-react'
import { api } from '../lib/api.ts'
import type { SystemHealth } from '../types'

export function SystemStatus() {
  const { data: health, isLoading } = useQuery<SystemHealth>({
    queryKey: ['system-health'],
    queryFn: api.getSystemHealth,
    refetchInterval: 30000, // Refresh every 30 seconds
  })

  if (isLoading || !health) {
    return (
      <div className="h-8 border-t border-border bg-muted/20 flex items-center justify-center">
        <div className="text-xs text-muted-foreground animate-pulse">Loading system status...</div>
      </div>
    )
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'text-green-600'
      case 'degraded':
        return 'text-yellow-600'
      case 'unhealthy':
        return 'text-red-600'
      default:
        return 'text-gray-500'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return CheckCircle
      case 'degraded':
      case 'unhealthy':
        return AlertTriangle
      default:
        return Activity
    }
  }

  const StatusIcon = getStatusIcon(health.status)

  return (
    <div className="h-8 border-t border-border bg-muted/20 flex items-center justify-between px-4 text-xs">
      <div className="flex items-center space-x-4">
        {/* Overall Status */}
        <div className={`flex items-center space-x-1 ${getStatusColor(health.status)}`}>
          <StatusIcon className="h-3 w-3" />
          <span className="capitalize">{health.status}</span>
        </div>

        {/* Database Status */}
        <div className={`flex items-center space-x-1 ${health.database_connected ? 'text-green-600' : 'text-red-600'}`}>
          <Database className="h-3 w-3" />
          <span>{health.database_connected ? 'DB Connected' : 'DB Disconnected'}</span>
        </div>

        {/* RAG Service Status */}
        <div className={`flex items-center space-x-1 ${health.rag_service_available ? 'text-green-600' : 'text-red-600'}`}>
          <Activity className="h-3 w-3" />
          <span>{health.rag_service_available ? 'RAG Available' : 'RAG Unavailable'}</span>
        </div>

        {/* API Key Status */}
        <div className={`flex items-center space-x-1 ${health.api_key_configured ? 'text-green-600' : 'text-yellow-600'}`}>
          <Wifi className="h-3 w-3" />
          <span>{health.api_key_configured ? 'API Configured' : 'API Not Configured'}</span>
        </div>
      </div>

      <div className="flex items-center space-x-4 text-muted-foreground">
        {/* Storage Health */}
        <span>Storage: {health.storage_health}</span>
        
        {/* Uptime */}
        {health.uptime_seconds !== undefined && (
          <span>
            Uptime: {Math.floor(health.uptime_seconds / 3600)}h {Math.floor((health.uptime_seconds % 3600) / 60)}m
          </span>
        )}
      </div>
    </div>
  )
}