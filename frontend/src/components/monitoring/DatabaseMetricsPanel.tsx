/**
 * Database Metrics Panel Component
 * 
 * Displays database performance metrics including connection pool status,
 * query performance, and database health indicators.
 */

import React from 'react';
import { 
  Database, 
  Zap, 
  Clock, 
  Users, 
  Activity,
  AlertTriangle,
  CheckCircle
} from 'lucide-react';

interface DatabaseData {
  timestamp: string;
  active_connections: number;
  connection_pool_size: number;
  connection_pool_available: number;
  query_count: number;
  slow_queries: number;
  avg_query_time_ms: number;
  database_size_mb: number;
  index_usage_percent: number;
  cache_hit_ratio: number;
  [key: string]: any;
}

interface DatabaseMetricsPanelProps {
  data?: DatabaseData;
  isConnected: boolean;
}

export const DatabaseMetricsPanel: React.FC<DatabaseMetricsPanelProps> = ({ 
  data, 
  isConnected 
}) => {
  const getConnectionPoolStatus = () => {
    if (!data) return { status: 'unknown', color: 'text-gray-500' };
    
    const utilizationPercent = ((data.connection_pool_size - data.connection_pool_available) / data.connection_pool_size) * 100;
    
    if (utilizationPercent > 90) {
      return { status: 'critical', color: 'text-red-600', bgColor: 'bg-red-100' };
    } else if (utilizationPercent > 70) {
      return { status: 'warning', color: 'text-yellow-600', bgColor: 'bg-yellow-100' };
    } else {
      return { status: 'healthy', color: 'text-green-600', bgColor: 'bg-green-100' };
    }
  };

  const getQueryPerformanceStatus = () => {
    if (!data) return { status: 'unknown', color: 'text-gray-500' };
    
    if (data.avg_query_time_ms > 1000) {
      return { status: 'critical', color: 'text-red-600' };
    } else if (data.avg_query_time_ms > 500) {
      return { status: 'warning', color: 'text-yellow-600' };
    } else {
      return { status: 'healthy', color: 'text-green-600' };
    }
  };

  const getCacheEfficiencyStatus = () => {
    if (!data) return { status: 'unknown', color: 'text-gray-500' };
    
    if (data.cache_hit_ratio < 70) {
      return { status: 'warning', color: 'text-yellow-600' };
    } else if (data.cache_hit_ratio < 50) {
      return { status: 'critical', color: 'text-red-600' };
    } else {
      return { status: 'healthy', color: 'text-green-600' };
    }
  };

  const formatBytes = (bytes: number, decimals = 1) => {
    if (bytes === 0) return '0 B';
    
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    
    const i = Math.floor(Math.log(bytes * 1024 * 1024) / Math.log(k));
    return parseFloat(((bytes * 1024 * 1024) / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  };

  const connectionPoolStatus = getConnectionPoolStatus();
  const queryPerformanceStatus = getQueryPerformanceStatus();
  const cacheEfficiencyStatus = getCacheEfficiencyStatus();

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <Database className="h-5 w-5 text-blue-500" />
          <h3 className="font-semibold text-gray-900">Database Performance</h3>
        </div>
        <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-gray-300'}`} />
      </div>

      {data ? (
        <div className="space-y-4">
          {/* Connection Pool Status */}
          <div className={`p-3 rounded-lg ${connectionPoolStatus.bgColor || 'bg-gray-100'}`}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2">
                <Users className="h-4 w-4 text-blue-500" />
                <span className="text-sm font-medium text-gray-700">Connection Pool</span>
              </div>
              {connectionPoolStatus.status === 'healthy' ? (
                <CheckCircle className="h-4 w-4 text-green-500" />
              ) : (
                <AlertTriangle className="h-4 w-4 text-yellow-500" />
              )}
            </div>
            
            <div className="grid grid-cols-3 gap-2 text-sm">
              <div className="text-center">
                <div className={`text-lg font-bold ${connectionPoolStatus.color}`}>
                  {data.active_connections}
                </div>
                <div className="text-xs text-gray-500">Active</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold text-gray-600">
                  {data.connection_pool_available}
                </div>
                <div className="text-xs text-gray-500">Available</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold text-gray-600">
                  {data.connection_pool_size}
                </div>
                <div className="text-xs text-gray-500">Pool Size</div>
              </div>
            </div>
            
            {/* Connection pool utilization bar */}
            <div className="mt-2">
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${
                    connectionPoolStatus.status === 'critical' ? 'bg-red-500' :
                    connectionPoolStatus.status === 'warning' ? 'bg-yellow-500' : 'bg-green-500'
                  }`}
                  style={{
                    width: `${((data.connection_pool_size - data.connection_pool_available) / data.connection_pool_size) * 100}%`
                  }}
                />
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {(((data.connection_pool_size - data.connection_pool_available) / data.connection_pool_size) * 100).toFixed(1)}% utilized
              </div>
            </div>
          </div>

          {/* Query Performance */}
          <div className="border border-gray-200 rounded-lg p-3">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center space-x-2">
                <Zap className="h-4 w-4 text-green-500" />
                <span className="text-sm font-medium text-gray-700">Query Performance</span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="text-center">
                <div className={`text-xl font-bold ${queryPerformanceStatus.color}`}>
                  {data.avg_query_time_ms.toFixed(1)}ms
                </div>
                <div className="text-xs text-gray-500">Avg Response Time</div>
              </div>
              <div className="text-center">
                <div className="text-xl font-bold text-blue-600">
                  {data.query_count}
                </div>
                <div className="text-xs text-gray-500">Queries/min</div>
              </div>
            </div>

            {/* Slow queries indicator */}
            {data.slow_queries > 0 && (
              <div className="mt-2 flex items-center space-x-2 text-sm text-yellow-600">
                <Clock className="h-4 w-4" />
                <span>{data.slow_queries} slow queries detected</span>
              </div>
            )}
          </div>

          {/* Cache Efficiency */}
          <div className="border border-gray-200 rounded-lg p-3">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center space-x-2">
                <Activity className="h-4 w-4 text-purple-500" />
                <span className="text-sm font-medium text-gray-700">Cache Efficiency</span>
              </div>
            </div>

            <div className="text-center">
              <div className={`text-2xl font-bold ${cacheEfficiencyStatus.color}`}>
                {data.cache_hit_ratio.toFixed(1)}%
              </div>
              <div className="text-xs text-gray-500">Hit Ratio</div>
            </div>

            {/* Cache hit ratio progress bar */}
            <div className="mt-2">
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${
                    data.cache_hit_ratio >= 80 ? 'bg-green-500' :
                    data.cache_hit_ratio >= 60 ? 'bg-yellow-500' : 'bg-red-500'
                  }`}
                  style={{ width: `${data.cache_hit_ratio}%` }}
                />
              </div>
            </div>
          </div>

          {/* Database Statistics */}
          <div className="border border-gray-200 rounded-lg p-3">
            <div className="flex items-center space-x-2 mb-3">
              <Database className="h-4 w-4 text-gray-500" />
              <span className="text-sm font-medium text-gray-700">Database Stats</span>
            </div>

            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <div className="text-gray-500">Size</div>
                <div className="font-semibold">
                  {formatBytes(data.database_size_mb)}
                </div>
              </div>
              <div>
                <div className="text-gray-500">Index Usage</div>
                <div className={`font-semibold ${
                  data.index_usage_percent > 80 ? 'text-green-600' :
                  data.index_usage_percent > 60 ? 'text-yellow-600' : 'text-red-600'
                }`}>
                  {data.index_usage_percent.toFixed(1)}%
                </div>
              </div>
            </div>
          </div>

          {/* Overall Health Indicator */}
          <div className="flex items-center justify-center space-x-4 pt-2 border-t border-gray-200">
            <div className="text-center">
              <div className="text-xs text-gray-500 mb-1">Overall Status</div>
              <div className={`px-2 py-1 rounded text-xs font-medium ${
                connectionPoolStatus.status === 'healthy' && 
                queryPerformanceStatus.status === 'healthy' && 
                cacheEfficiencyStatus.status === 'healthy'
                  ? 'bg-green-100 text-green-700'
                  : connectionPoolStatus.status === 'critical' || 
                    queryPerformanceStatus.status === 'critical'
                    ? 'bg-red-100 text-red-700'
                    : 'bg-yellow-100 text-yellow-700'
              }`}>
                {connectionPoolStatus.status === 'healthy' && 
                 queryPerformanceStatus.status === 'healthy' && 
                 cacheEfficiencyStatus.status === 'healthy'
                  ? 'HEALTHY'
                  : connectionPoolStatus.status === 'critical' || 
                    queryPerformanceStatus.status === 'critical'
                    ? 'CRITICAL'
                    : 'WARNING'}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="text-center text-gray-500 py-8">
          <Database className="h-12 w-12 mx-auto mb-2 opacity-50" />
          <p>No database metrics available</p>
          {!isConnected && (
            <p className="text-sm text-red-500 mt-1">Connection lost</p>
          )}
        </div>
      )}
    </div>
  );
};