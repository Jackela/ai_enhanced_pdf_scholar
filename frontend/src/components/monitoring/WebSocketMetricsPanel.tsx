/**
 * WebSocket Metrics Panel Component
 * 
 * Displays WebSocket connection statistics and RAG task metrics
 * with real-time updates and task lifecycle tracking.
 */

import React from 'react';
import { 
  Wifi, 
  Users, 
  MessageSquare, 
  Clock, 
  CheckCircle, 
  XCircle, 
  AlertCircle,
  Loader,
  Activity,
  TrendingUp
} from 'lucide-react';

interface WebSocketData {
  timestamp: string;
  active_connections: number;
  total_rooms: number;
  rag_tasks_total: number;
  rag_tasks_pending: number;
  rag_tasks_processing: number;
  rag_tasks_streaming: number;
  rag_tasks_completed: number;
  rag_tasks_failed: number;
  avg_task_duration_ms: number;
  concurrent_task_limit: number;
  [key: string]: any;
}

interface WebSocketMetricsPanelProps {
  data?: WebSocketData;
  isConnected: boolean;
}

export const WebSocketMetricsPanel: React.FC<WebSocketMetricsPanelProps> = ({ 
  data, 
  isConnected 
}) => {
  const getTaskUtilization = () => {
    if (!data) return 0;
    const activeTasks = data.rag_tasks_processing + data.rag_tasks_streaming;
    return data.concurrent_task_limit > 0 ? (activeTasks / data.concurrent_task_limit) * 100 : 0;
  };

  const getTaskSuccessRate = () => {
    if (!data) return 0;
    const totalCompleted = data.rag_tasks_completed + data.rag_tasks_failed;
    return totalCompleted > 0 ? (data.rag_tasks_completed / totalCompleted) * 100 : 0;
  };

  const getTaskStatusColor = (status: string, count: number) => {
    if (count === 0) return 'text-gray-400';
    
    switch (status) {
      case 'pending': return 'text-blue-600';
      case 'processing': return 'text-yellow-600';
      case 'streaming': return 'text-purple-600';
      case 'completed': return 'text-green-600';
      case 'failed': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  const getTaskStatusIcon = (status: string) => {
    switch (status) {
      case 'pending': return <Clock className="h-4 w-4" />;
      case 'processing': return <Loader className="h-4 w-4 animate-spin" />;
      case 'streaming': return <Activity className="h-4 w-4" />;
      case 'completed': return <CheckCircle className="h-4 w-4" />;
      case 'failed': return <XCircle className="h-4 w-4" />;
      default: return <AlertCircle className="h-4 w-4" />;
    }
  };

  const formatDuration = (ms: number): string => {
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  const taskUtilization = getTaskUtilization();
  const successRate = getTaskSuccessRate();

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <Wifi className="h-5 w-5 text-blue-500" />
          <h3 className="font-semibold text-gray-900">WebSocket & RAG Tasks</h3>
        </div>
        <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-gray-300'}`} />
      </div>

      {data ? (
        <div className="space-y-4">
          {/* Connection Overview */}
          <div className="border border-gray-200 rounded-lg p-3">
            <div className="flex items-center space-x-2 mb-3">
              <Users className="h-4 w-4 text-blue-500" />
              <span className="text-sm font-medium text-gray-700">Connections</span>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">
                  {data.active_connections}
                </div>
                <div className="text-xs text-gray-500">Active</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-purple-600">
                  {data.total_rooms}
                </div>
                <div className="text-xs text-gray-500">Rooms</div>
              </div>
            </div>
          </div>

          {/* Task Utilization */}
          <div className={`p-3 rounded-lg ${
            taskUtilization > 90 ? 'bg-red-100' :
            taskUtilization > 70 ? 'bg-yellow-100' : 'bg-green-100'
          }`}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2">
                <TrendingUp className="h-4 w-4 text-gray-600" />
                <span className="text-sm font-medium text-gray-700">Task Utilization</span>
              </div>
            </div>

            <div className="text-center mb-2">
              <div className={`text-2xl font-bold ${
                taskUtilization > 90 ? 'text-red-600' :
                taskUtilization > 70 ? 'text-yellow-600' : 'text-green-600'
              }`}>
                {taskUtilization.toFixed(1)}%
              </div>
              <div className="text-xs text-gray-500">
                {data.rag_tasks_processing + data.rag_tasks_streaming} / {data.concurrent_task_limit} slots used
              </div>
            </div>

            {/* Utilization progress bar */}
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className={`h-2 rounded-full ${
                  taskUtilization > 90 ? 'bg-red-500' :
                  taskUtilization > 70 ? 'bg-yellow-500' : 'bg-green-500'
                }`}
                style={{ width: `${Math.min(taskUtilization, 100)}%` }}
              />
            </div>
          </div>

          {/* Task Status Breakdown */}
          <div className="border border-gray-200 rounded-lg p-3">
            <div className="flex items-center space-x-2 mb-3">
              <MessageSquare className="h-4 w-4 text-green-500" />
              <span className="text-sm font-medium text-gray-700">RAG Task Status</span>
            </div>

            <div className="grid grid-cols-2 gap-3 text-sm">
              {/* Pending Tasks */}
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  {getTaskStatusIcon('pending')}
                  <span className="text-gray-600">Pending</span>
                </div>
                <span className={`font-semibold ${getTaskStatusColor('pending', data.rag_tasks_pending)}`}>
                  {data.rag_tasks_pending}
                </span>
              </div>

              {/* Processing Tasks */}
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  {getTaskStatusIcon('processing')}
                  <span className="text-gray-600">Processing</span>
                </div>
                <span className={`font-semibold ${getTaskStatusColor('processing', data.rag_tasks_processing)}`}>
                  {data.rag_tasks_processing}
                </span>
              </div>

              {/* Streaming Tasks */}
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  {getTaskStatusIcon('streaming')}
                  <span className="text-gray-600">Streaming</span>
                </div>
                <span className={`font-semibold ${getTaskStatusColor('streaming', data.rag_tasks_streaming)}`}>
                  {data.rag_tasks_streaming}
                </span>
              </div>

              {/* Completed Tasks */}
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  {getTaskStatusIcon('completed')}
                  <span className="text-gray-600">Completed</span>
                </div>
                <span className={`font-semibold ${getTaskStatusColor('completed', data.rag_tasks_completed)}`}>
                  {data.rag_tasks_completed}
                </span>
              </div>

              {/* Failed Tasks */}
              <div className="flex items-center justify-between col-span-2">
                <div className="flex items-center space-x-2">
                  {getTaskStatusIcon('failed')}
                  <span className="text-gray-600">Failed</span>
                </div>
                <span className={`font-semibold ${getTaskStatusColor('failed', data.rag_tasks_failed)}`}>
                  {data.rag_tasks_failed}
                </span>
              </div>
            </div>
          </div>

          {/* Performance Metrics */}
          <div className="border border-gray-200 rounded-lg p-3">
            <div className="flex items-center space-x-2 mb-3">
              <Clock className="h-4 w-4 text-orange-500" />
              <span className="text-sm font-medium text-gray-700">Performance</span>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="text-center">
                <div className={`text-xl font-bold ${
                  data.avg_task_duration_ms > 10000 ? 'text-red-600' :
                  data.avg_task_duration_ms > 5000 ? 'text-yellow-600' : 'text-green-600'
                }`}>
                  {formatDuration(data.avg_task_duration_ms)}
                </div>
                <div className="text-xs text-gray-500">Avg Duration</div>
              </div>
              <div className="text-center">
                <div className={`text-xl font-bold ${
                  successRate < 80 ? 'text-red-600' :
                  successRate < 90 ? 'text-yellow-600' : 'text-green-600'
                }`}>
                  {successRate.toFixed(1)}%
                </div>
                <div className="text-xs text-gray-500">Success Rate</div>
              </div>
            </div>

            {/* Success rate progress bar */}
            <div className="mt-2">
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${
                    successRate >= 90 ? 'bg-green-500' :
                    successRate >= 80 ? 'bg-yellow-500' : 'bg-red-500'
                  }`}
                  style={{ width: `${successRate}%` }}
                />
              </div>
            </div>
          </div>

          {/* Total Tasks Summary */}
          <div className="text-center text-sm text-gray-600 pt-2 border-t border-gray-200">
            <div className="font-medium text-gray-800">
              Total Tasks: {data.rag_tasks_total}
            </div>
            <div className="text-xs mt-1">
              Since last restart
            </div>
          </div>

          {/* Status Alerts */}
          {taskUtilization > 90 && (
            <div className="flex items-center space-x-2 text-sm text-red-600 bg-red-50 p-2 rounded">
              <AlertCircle className="h-4 w-4" />
              <span>High task utilization - consider scaling</span>
            </div>
          )}

          {data.rag_tasks_failed > 0 && successRate < 80 && (
            <div className="flex items-center space-x-2 text-sm text-yellow-600 bg-yellow-50 p-2 rounded">
              <AlertCircle className="h-4 w-4" />
              <span>Low success rate - check system health</span>
            </div>
          )}
        </div>
      ) : (
        <div className="text-center text-gray-500 py-8">
          <Wifi className="h-12 w-12 mx-auto mb-2 opacity-50" />
          <p>No WebSocket metrics available</p>
          {!isConnected && (
            <p className="text-sm text-red-500 mt-1">Connection lost</p>
          )}
        </div>
      )}
    </div>
  );
};