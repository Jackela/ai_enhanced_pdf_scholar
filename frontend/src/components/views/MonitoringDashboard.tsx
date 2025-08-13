/**
 * Performance Monitoring Dashboard
 * 
 * Real-time system performance monitoring dashboard with charts,
 * metrics, and alert notifications.
 */

import React, { useState, useEffect, useRef } from 'react';
import { 
  Activity, 
  Server, 
  Database, 
  Wifi, 
  AlertTriangle, 
  CheckCircle, 
  XCircle,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Bell,
  Settings as SettingsIcon,
  Maximize2,
  Minimize2
} from 'lucide-react';
import { Button } from '../ui/Button';
import { SystemMetricsChart } from '../monitoring/SystemMetricsChart';
import { DatabaseMetricsPanel } from '../monitoring/DatabaseMetricsPanel';
import { WebSocketMetricsPanel } from '../monitoring/WebSocketMetricsPanel';
import { AlertsPanel } from '../monitoring/AlertsPanel';
import { MetricsWebSocketClient } from '../../lib/metricsWebSocket';

interface SystemHealthStatus {
  health_score: number;
  status: 'excellent' | 'good' | 'degraded' | 'critical';
  factors: string[];
  last_updated: string;
  metrics_available: string[];
}

interface MetricsData {
  system?: {
    timestamp: string;
    cpu_percent: number;
    memory_percent: number;
    disk_usage_percent: number;
    uptime_seconds: number;
    [key: string]: any;
  };
  database?: {
    timestamp: string;
    active_connections: number;
    avg_query_time_ms: number;
    connection_pool_available: number;
    [key: string]: any;
  };
  websocket?: {
    timestamp: string;
    active_connections: number;
    rag_tasks_total: number;
    rag_tasks_processing: number;
    [key: string]: any;
  };
  api?: {
    timestamp: string;
    requests_per_second: number;
    avg_response_time_ms: number;
    error_rate_percent: number;
    [key: string]: any;
  };
  memory?: {
    timestamp: string;
    heap_size_mb: number;
    connection_leaks: number;
    memory_pressure_events: number;
    [key: string]: any;
  };
}

interface Alert {
  type: string;
  severity: 'info' | 'warning' | 'error' | 'critical';
  message: string;
  timestamp: string;
  value?: number;
  threshold?: number;
}

export const MonitoringDashboard: React.FC = () => {
  const [metricsData, setMetricsData] = useState<MetricsData>({});
  const [healthStatus, setHealthStatus] = useState<SystemHealthStatus | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(1000); // 1 second
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>([
    'system', 'database', 'websocket', 'api'
  ]);
  const [isFullscreen, setIsFullscreen] = useState(false);
  
  const wsClientRef = useRef<MetricsWebSocketClient | null>(null);
  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const retryCount = useRef(0);
  const maxRetries = 5;

  // Initialize WebSocket connection
  useEffect(() => {
    initializeConnection();
    
    return () => {
      cleanup();
    };
  }, []);

  // Handle auto-refresh settings
  useEffect(() => {
    if (autoRefresh && wsClientRef.current && isConnected) {
      wsClientRef.current.subscribe(selectedMetrics, refreshInterval / 1000);
    }
  }, [autoRefresh, refreshInterval, selectedMetrics, isConnected]);

  const initializeConnection = async () => {
    try {
      setIsLoading(true);
      setError(null);

      // Generate unique client ID
      const clientId = `dashboard_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      
      // Initialize WebSocket client
      wsClientRef.current = new MetricsWebSocketClient(
        `ws://localhost:8000/api/system/ws/metrics/${clientId}`
      );

      // Set up event handlers
      wsClientRef.current.onConnect = () => {
        setIsConnected(true);
        setIsLoading(false);
        retryCount.current = 0;
        
        // Subscribe to selected metrics
        if (autoRefresh) {
          wsClientRef.current?.subscribe(selectedMetrics, refreshInterval / 1000);
        }
      };

      wsClientRef.current.onDisconnect = () => {
        setIsConnected(false);
        handleDisconnection();
      };

      wsClientRef.current.onMetricsUpdate = (metrics: MetricsData) => {
        setMetricsData(prevData => ({
          ...prevData,
          ...metrics
        }));
      };

      wsClientRef.current.onHealthUpdate = (health: SystemHealthStatus) => {
        setHealthStatus(health);
      };

      wsClientRef.current.onAlert = (alert: Alert) => {
        setAlerts(prevAlerts => [alert, ...prevAlerts.slice(0, 9)]); // Keep last 10 alerts
      };

      wsClientRef.current.onError = (error: string) => {
        setError(error);
        console.error('Metrics WebSocket error:', error);
      };

      // Connect
      await wsClientRef.current.connect();

      // Also fetch initial HTTP data
      await fetchInitialData();

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to initialize monitoring';
      setError(errorMessage);
      setIsLoading(false);
      handleConnectionError();
    }
  };

  const fetchInitialData = async () => {
    try {
      // Fetch current metrics via HTTP as fallback
      const response = await fetch('/api/system/metrics/current');
      if (response.ok) {
        const data = await response.json();
        if (data.status === 'success') {
          setMetricsData(data.data.metrics || {});
          setHealthStatus(data.data.health_summary);
        }
      }
    } catch (err) {
      console.warn('Failed to fetch initial HTTP metrics:', err);
    }
  };

  const handleDisconnection = () => {
    if (retryCount.current < maxRetries) {
      const delay = Math.min(1000 * Math.pow(2, retryCount.current), 30000);
      retryTimeoutRef.current = setTimeout(() => {
        retryCount.current++;
        initializeConnection();
      }, delay);
    }
  };

  const handleConnectionError = () => {
    if (retryCount.current < maxRetries) {
      handleDisconnection();
    } else {
      setError('Failed to connect after multiple attempts. Please refresh the page.');
    }
  };

  const cleanup = () => {
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
    }
    
    if (wsClientRef.current) {
      wsClientRef.current.disconnect();
    }
  };

  const handleRefresh = async () => {
    if (wsClientRef.current && isConnected) {
      wsClientRef.current.requestCurrentMetrics();
    } else {
      await initializeConnection();
    }
  };

  const handleMetricsToggle = (metricType: string) => {
    const newSelection = selectedMetrics.includes(metricType)
      ? selectedMetrics.filter(m => m !== metricType)
      : [...selectedMetrics, metricType];
    
    setSelectedMetrics(newSelection);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'excellent': return 'text-green-500';
      case 'good': return 'text-blue-500';
      case 'degraded': return 'text-yellow-500';
      case 'critical': return 'text-red-500';
      default: return 'text-gray-500';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'excellent':
      case 'good':
        return <CheckCircle className="h-6 w-6 text-green-500" />;
      case 'degraded':
        return <AlertTriangle className="h-6 w-6 text-yellow-500" />;
      case 'critical':
        return <XCircle className="h-6 w-6 text-red-500" />;
      default:
        return <Activity className="h-6 w-6 text-gray-500" />;
    }
  };

  const formatUptime = (seconds: number): string => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (days > 0) return `${days}d ${hours}h ${minutes}m`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-4 text-blue-500" />
          <p className="text-gray-600">Initializing performance monitoring...</p>
        </div>
      </div>
    );
  }

  if (error && !isConnected) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <XCircle className="h-8 w-8 mx-auto mb-4 text-red-500" />
          <p className="text-red-600 mb-4">{error}</p>
          <Button onClick={handleRefresh} variant="outline">
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry Connection
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className={`min-h-screen bg-gray-50 ${isFullscreen ? 'fixed inset-0 z-50' : ''}`}>
      {/* Dashboard Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <Activity className="h-8 w-8 text-blue-600" />
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Performance Monitor</h1>
              <p className="text-sm text-gray-500">
                Real-time system metrics and health monitoring
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            {/* Connection Status */}
            <div className="flex items-center space-x-2">
              <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
              <span className="text-sm text-gray-600">
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>

            {/* Auto-refresh toggle */}
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="rounded border-gray-300"
              />
              <span className="text-sm text-gray-600">Auto-refresh</span>
            </label>

            {/* Refresh interval */}
            <select
              value={refreshInterval}
              onChange={(e) => setRefreshInterval(Number(e.target.value))}
              className="text-sm border border-gray-300 rounded-md px-2 py-1"
              disabled={!autoRefresh}
            >
              <option value={500}>0.5s</option>
              <option value={1000}>1s</option>
              <option value={2000}>2s</option>
              <option value={5000}>5s</option>
            </select>

            {/* Manual refresh */}
            <Button
              onClick={handleRefresh}
              variant="outline"
              size="sm"
              disabled={!isConnected}
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>

            {/* Fullscreen toggle */}
            <Button
              onClick={() => setIsFullscreen(!isFullscreen)}
              variant="outline"
              size="sm"
            >
              {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
            </Button>
          </div>
        </div>

        {/* Health Status Bar */}
        {healthStatus && (
          <div className="mt-4 p-3 bg-gray-50 rounded-lg">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                {getStatusIcon(healthStatus.status)}
                <div>
                  <span className="text-sm font-medium text-gray-900">
                    System Health: 
                  </span>
                  <span className={`ml-2 text-sm font-semibold ${getStatusColor(healthStatus.status)}`}>
                    {healthStatus.status.toUpperCase()} ({healthStatus.health_score.toFixed(1)}%)
                  </span>
                </div>
              </div>
              
              {metricsData.system && (
                <div className="text-sm text-gray-600">
                  Uptime: {formatUptime(metricsData.system.uptime_seconds)}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Dashboard Content */}
      <div className="p-6 grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* System Metrics Chart - Takes 2/3 width */}
        <div className="xl:col-span-2">
          <SystemMetricsChart 
            data={metricsData.system}
            isConnected={isConnected}
          />
        </div>

        {/* Alerts Panel */}
        <div className="xl:col-span-1">
          <AlertsPanel alerts={alerts} />
        </div>

        {/* Database Metrics */}
        <div className="xl:col-span-1">
          <DatabaseMetricsPanel 
            data={metricsData.database}
            isConnected={isConnected}
          />
        </div>

        {/* WebSocket Metrics */}
        <div className="xl:col-span-1">
          <WebSocketMetricsPanel 
            data={metricsData.websocket}
            isConnected={isConnected}
          />
        </div>

        {/* API Metrics */}
        <div className="xl:col-span-1">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-2">
                <Server className="h-5 w-5 text-blue-500" />
                <h3 className="font-semibold text-gray-900">API Performance</h3>
              </div>
              <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-gray-300'}`} />
            </div>

            {metricsData.api ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-600">
                      {metricsData.api.requests_per_second.toFixed(1)}
                    </div>
                    <div className="text-xs text-gray-500">RPS</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-green-600">
                      {metricsData.api.avg_response_time_ms.toFixed(0)}ms
                    </div>
                    <div className="text-xs text-gray-500">Avg Response</div>
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div className="text-center">
                    <div className={`text-xl font-bold ${
                      metricsData.api.error_rate_percent > 5 ? 'text-red-600' :
                      metricsData.api.error_rate_percent > 1 ? 'text-yellow-600' : 'text-green-600'
                    }`}>
                      {metricsData.api.error_rate_percent.toFixed(1)}%
                    </div>
                    <div className="text-xs text-gray-500">Error Rate</div>
                  </div>
                  <div className="text-center">
                    <div className="text-xl font-bold text-purple-600">
                      {metricsData.api.active_sessions}
                    </div>
                    <div className="text-xs text-gray-500">Active Sessions</div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center text-gray-500 py-8">
                <Server className="h-12 w-12 mx-auto mb-2 opacity-50" />
                <p>No API metrics available</p>
              </div>
            )}
          </div>
        </div>

        {/* Memory Leak Detection */}
        <div className="xl:col-span-3">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-2">
                <Activity className="h-5 w-5 text-red-500" />
                <h3 className="font-semibold text-gray-900">Memory Leak Detection</h3>
              </div>
              <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-gray-300'}`} />
            </div>

            {metricsData.memory ? (
              <div className="grid grid-cols-4 gap-4">
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-600">
                    {metricsData.memory.heap_size_mb.toFixed(1)}MB
                  </div>
                  <div className="text-xs text-gray-500">Heap Size</div>
                </div>
                <div className="text-center">
                  <div className={`text-2xl font-bold ${
                    metricsData.memory.connection_leaks > 0 ? 'text-red-600' : 'text-green-600'
                  }`}>
                    {metricsData.memory.connection_leaks}
                  </div>
                  <div className="text-xs text-gray-500">Connection Leaks</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-yellow-600">
                    {metricsData.memory.gc_collections}
                  </div>
                  <div className="text-xs text-gray-500">GC Collections</div>
                </div>
                <div className="text-center">
                  <div className={`text-2xl font-bold ${
                    metricsData.memory.memory_pressure_events > 0 ? 'text-red-600' : 'text-green-600'
                  }`}>
                    {metricsData.memory.memory_pressure_events}
                  </div>
                  <div className="text-xs text-gray-500">Pressure Events</div>
                </div>
              </div>
            ) : (
              <div className="text-center text-gray-500 py-8">
                <Activity className="h-12 w-12 mx-auto mb-2 opacity-50" />
                <p>No memory metrics available</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};