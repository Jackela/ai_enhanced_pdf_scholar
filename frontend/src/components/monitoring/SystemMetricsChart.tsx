/**
 * System Metrics Chart Component
 * 
 * Real-time chart displaying CPU, memory, and disk usage
 * with trend indicators and historical context.
 */

import React, { useState, useEffect, useRef } from 'react';
import { 
  Activity, 
  Cpu, 
  HardDrive, 
  MemoryStick,
  TrendingUp,
  TrendingDown,
  Minus
} from 'lucide-react';

interface SystemData {
  timestamp: string;
  cpu_percent: number;
  memory_percent: number;
  disk_usage_percent: number;
  uptime_seconds: number;
  memory_used_mb: number;
  memory_available_mb: number;
  [key: string]: any;
}

interface SystemMetricsChartProps {
  data?: SystemData;
  isConnected: boolean;
}

interface MetricHistory {
  timestamp: number;
  cpu: number;
  memory: number;
  disk: number;
}

const MAX_HISTORY_POINTS = 50;

export const SystemMetricsChart: React.FC<SystemMetricsChartProps> = ({ 
  data, 
  isConnected 
}) => {
  const [history, setHistory] = useState<MetricHistory[]>([]);
  const [trends, setTrends] = useState({
    cpu: 0,
    memory: 0,
    disk: 0
  });
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationFrameRef = useRef<number>();

  // Update history when new data arrives
  useEffect(() => {
    if (data) {
      const newPoint: MetricHistory = {
        timestamp: Date.now(),
        cpu: data.cpu_percent,
        memory: data.memory_percent,
        disk: data.disk_usage_percent
      };

      setHistory(prevHistory => {
        const updated = [...prevHistory, newPoint].slice(-MAX_HISTORY_POINTS);
        
        // Calculate trends
        if (updated.length >= 5) {
          const recent = updated.slice(-5);
          const older = updated.slice(-10, -5);
          
          if (older.length > 0) {
            const recentAvg = {
              cpu: recent.reduce((sum, p) => sum + p.cpu, 0) / recent.length,
              memory: recent.reduce((sum, p) => sum + p.memory, 0) / recent.length,
              disk: recent.reduce((sum, p) => sum + p.disk, 0) / recent.length
            };
            
            const olderAvg = {
              cpu: older.reduce((sum, p) => sum + p.cpu, 0) / older.length,
              memory: older.reduce((sum, p) => sum + p.memory, 0) / older.length,
              disk: older.reduce((sum, p) => sum + p.disk, 0) / older.length
            };
            
            setTrends({
              cpu: recentAvg.cpu - olderAvg.cpu,
              memory: recentAvg.memory - olderAvg.memory,
              disk: recentAvg.disk - olderAvg.disk
            });
          }
        }
        
        return updated;
      });
    }
  }, [data]);

  // Draw chart on canvas
  useEffect(() => {
    if (!canvasRef.current || history.length === 0) return;

    const draw = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;

      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      // Set canvas size
      const rect = canvas.getBoundingClientRect();
      const pixelRatio = window.devicePixelRatio || 1;
      canvas.width = rect.width * pixelRatio;
      canvas.height = rect.height * pixelRatio;
      ctx.scale(pixelRatio, pixelRatio);

      const { width, height } = rect;
      const padding = 40;
      const chartWidth = width - padding * 2;
      const chartHeight = height - padding * 2;

      // Clear canvas
      ctx.fillStyle = '#f9fafb';
      ctx.fillRect(0, 0, width, height);

      // Draw grid
      ctx.strokeStyle = '#e5e7eb';
      ctx.lineWidth = 1;
      
      // Horizontal grid lines
      for (let i = 0; i <= 4; i++) {
        const y = padding + (chartHeight / 4) * i;
        ctx.beginPath();
        ctx.moveTo(padding, y);
        ctx.lineTo(width - padding, y);
        ctx.stroke();
        
        // Labels
        ctx.fillStyle = '#6b7280';
        ctx.font = '12px system-ui';
        ctx.textAlign = 'right';
        ctx.fillText(`${100 - (i * 25)}%`, padding - 10, y + 4);
      }

      if (history.length < 2) return;

      // Helper function to draw metric line
      const drawMetricLine = (
        values: number[], 
        color: string, 
        lineWidth = 2,
        fill = false,
        fillColor = ''
      ) => {
        ctx.strokeStyle = color;
        ctx.lineWidth = lineWidth;
        
        if (fill && fillColor) {
          ctx.fillStyle = fillColor;
          ctx.beginPath();
          ctx.moveTo(padding, padding + chartHeight);
          
          values.forEach((value, index) => {
            const x = padding + (chartWidth / (values.length - 1)) * index;
            const y = padding + chartHeight - (value / 100) * chartHeight;
            if (index === 0) {
              ctx.lineTo(x, y);
            } else {
              ctx.lineTo(x, y);
            }
          });
          
          ctx.lineTo(padding + chartWidth, padding + chartHeight);
          ctx.closePath();
          ctx.fill();
        }
        
        ctx.beginPath();
        values.forEach((value, index) => {
          const x = padding + (chartWidth / (values.length - 1)) * index;
          const y = padding + chartHeight - (value / 100) * chartHeight;
          if (index === 0) {
            ctx.moveTo(x, y);
          } else {
            ctx.lineTo(x, y);
          }
        });
        ctx.stroke();
      };

      // Extract metric values
      const cpuValues = history.map(h => h.cpu);
      const memoryValues = history.map(h => h.memory);
      const diskValues = history.map(h => h.disk);

      // Draw metric lines
      drawMetricLine(cpuValues, '#3b82f6', 3); // Blue for CPU
      drawMetricLine(memoryValues, '#10b981', 3); // Green for memory
      drawMetricLine(diskValues, '#f59e0b', 3); // Orange for disk

      // Draw current value indicators
      if (data) {
        const currentX = padding + chartWidth;
        
        // CPU indicator
        const cpuY = padding + chartHeight - (data.cpu_percent / 100) * chartHeight;
        ctx.fillStyle = '#3b82f6';
        ctx.beginPath();
        ctx.arc(currentX - 2, cpuY, 4, 0, 2 * Math.PI);
        ctx.fill();
        
        // Memory indicator
        const memY = padding + chartHeight - (data.memory_percent / 100) * chartHeight;
        ctx.fillStyle = '#10b981';
        ctx.beginPath();
        ctx.arc(currentX - 2, memY, 4, 0, 2 * Math.PI);
        ctx.fill();
        
        // Disk indicator
        const diskY = padding + chartHeight - (data.disk_usage_percent / 100) * chartHeight;
        ctx.fillStyle = '#f59e0b';
        ctx.beginPath();
        ctx.arc(currentX - 2, diskY, 4, 0, 2 * Math.PI);
        ctx.fill();
      }
    };

    draw();
    
    // Animation loop for smooth updates
    const animate = () => {
      draw();
      animationFrameRef.current = requestAnimationFrame(animate);
    };
    
    animationFrameRef.current = requestAnimationFrame(animate);
    
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [history, data]);

  const getTrendIcon = (trend: number) => {
    if (trend > 1) return <TrendingUp className="h-4 w-4 text-red-500" />;
    if (trend < -1) return <TrendingDown className="h-4 w-4 text-green-500" />;
    return <Minus className="h-4 w-4 text-gray-500" />;
  };

  const getStatusColor = (value: number, type: 'cpu' | 'memory' | 'disk') => {
    const thresholds = {
      cpu: { warning: 70, critical: 85 },
      memory: { warning: 80, critical: 90 },
      disk: { warning: 85, critical: 95 }
    };

    const threshold = thresholds[type];
    if (value >= threshold.critical) return 'text-red-600 bg-red-100';
    if (value >= threshold.warning) return 'text-yellow-600 bg-yellow-100';
    return 'text-green-600 bg-green-100';
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <Activity className="h-5 w-5 text-blue-500" />
          <h3 className="font-semibold text-gray-900">System Performance</h3>
        </div>
        <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-gray-300'}`} />
      </div>

      {/* Current Values */}
      {data ? (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="text-center">
            <div className="flex items-center justify-center space-x-1 mb-1">
              <Cpu className="h-4 w-4 text-blue-500" />
              <span className="text-sm font-medium text-gray-600">CPU</span>
              {getTrendIcon(trends.cpu)}
            </div>
            <div className={`text-2xl font-bold px-2 py-1 rounded ${getStatusColor(data.cpu_percent, 'cpu')}`}>
              {data.cpu_percent.toFixed(1)}%
            </div>
          </div>
          
          <div className="text-center">
            <div className="flex items-center justify-center space-x-1 mb-1">
              <MemoryStick className="h-4 w-4 text-green-500" />
              <span className="text-sm font-medium text-gray-600">Memory</span>
              {getTrendIcon(trends.memory)}
            </div>
            <div className={`text-2xl font-bold px-2 py-1 rounded ${getStatusColor(data.memory_percent, 'memory')}`}>
              {data.memory_percent.toFixed(1)}%
            </div>
            <div className="text-xs text-gray-500 mt-1">
              {(data.memory_used_mb / 1024).toFixed(1)}GB / {((data.memory_used_mb + data.memory_available_mb) / 1024).toFixed(1)}GB
            </div>
          </div>
          
          <div className="text-center">
            <div className="flex items-center justify-center space-x-1 mb-1">
              <HardDrive className="h-4 w-4 text-orange-500" />
              <span className="text-sm font-medium text-gray-600">Disk</span>
              {getTrendIcon(trends.disk)}
            </div>
            <div className={`text-2xl font-bold px-2 py-1 rounded ${getStatusColor(data.disk_usage_percent, 'disk')}`}>
              {data.disk_usage_percent.toFixed(1)}%
            </div>
          </div>
        </div>
      ) : (
        <div className="text-center text-gray-500 py-8">
          <Activity className="h-12 w-12 mx-auto mb-2 opacity-50" />
          <p>No system metrics available</p>
          {!isConnected && (
            <p className="text-sm text-red-500 mt-1">Connection lost</p>
          )}
        </div>
      )}

      {/* Chart */}
      <div className="relative">
        <canvas
          ref={canvasRef}
          className="w-full h-64 rounded border border-gray-200"
          style={{ display: history.length > 0 ? 'block' : 'none' }}
        />
        
        {history.length === 0 && (
          <div className="w-full h-64 border border-gray-200 rounded flex items-center justify-center text-gray-500">
            <div className="text-center">
              <Activity className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p>Collecting metrics...</p>
            </div>
          </div>
        )}

        {/* Legend */}
        <div className="absolute bottom-2 right-2 bg-white bg-opacity-90 rounded p-2 text-xs">
          <div className="flex space-x-4">
            <div className="flex items-center space-x-1">
              <div className="w-3 h-0.5 bg-blue-500" />
              <span>CPU</span>
            </div>
            <div className="flex items-center space-x-1">
              <div className="w-3 h-0.5 bg-green-500" />
              <span>Memory</span>
            </div>
            <div className="flex items-center space-x-1">
              <div className="w-3 h-0.5 bg-orange-500" />
              <span>Disk</span>
            </div>
          </div>
        </div>
      </div>

      {/* Stats */}
      {history.length > 0 && (
        <div className="mt-4 text-sm text-gray-600">
          <div className="flex justify-between">
            <span>Data points: {history.length}</span>
            <span>Update frequency: {isConnected ? 'Real-time' : 'Disconnected'}</span>
          </div>
        </div>
      )}
    </div>
  );
};