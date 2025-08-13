/**
 * Real-time Metrics WebSocket Client
 * 
 * Handles WebSocket connection for streaming performance metrics
 * with automatic reconnection and subscription management.
 */

export interface MetricsData {
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

export interface SystemHealthStatus {
  health_score: number;
  status: 'excellent' | 'good' | 'degraded' | 'critical';
  factors: string[];
  last_updated: string;
  metrics_available: string[];
}

export interface Alert {
  type: string;
  severity: 'info' | 'warning' | 'error' | 'critical';
  message: string;
  timestamp: string;
  value?: number;
  threshold?: number;
}

export interface WebSocketMessage {
  type: string;
  [key: string]: any;
}

export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'error';

export class MetricsWebSocketClient {
  private websocket: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000; // Start with 1 second
  private maxReconnectDelay = 30000; // Max 30 seconds
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private pingInterval: NodeJS.Timeout | null = null;
  private connectionState: ConnectionState = 'disconnected';
  private subscriptions: string[] = [];
  private updateInterval = 1.0; // seconds

  // Event handlers
  public onConnect?: () => void;
  public onDisconnect?: () => void;
  public onMetricsUpdate?: (metrics: MetricsData) => void;
  public onHealthUpdate?: (health: SystemHealthStatus) => void;
  public onAlert?: (alert: Alert) => void;
  public onError?: (error: string) => void;
  public onConnectionStateChange?: (state: ConnectionState) => void;

  constructor(url: string) {
    this.url = url;
  }

  /**
   * Connect to the WebSocket server
   */
  public async connect(): Promise<void> {
    if (this.connectionState === 'connected' || this.connectionState === 'connecting') {
      return;
    }

    this.setConnectionState('connecting');

    try {
      this.websocket = new WebSocket(this.url);
      
      this.websocket.onopen = () => {
        console.log('Metrics WebSocket connected');
        this.reconnectAttempts = 0;
        this.reconnectDelay = 1000;
        this.setConnectionState('connected');
        this.startPingInterval();
        this.onConnect?.();
      };

      this.websocket.onclose = (event) => {
        console.log('Metrics WebSocket disconnected:', event.code, event.reason);
        this.setConnectionState('disconnected');
        this.stopPingInterval();
        this.onDisconnect?.();
        
        // Attempt reconnection if not manually closed
        if (event.code !== 1000) {
          this.scheduleReconnect();
        }
      };

      this.websocket.onerror = (error) => {
        console.error('Metrics WebSocket error:', error);
        this.setConnectionState('error');
        this.onError?.('WebSocket connection error');
      };

      this.websocket.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          this.handleMessage(message);
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
          this.onError?.('Failed to parse server message');
        }
      };

    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      this.setConnectionState('error');
      this.onError?.('Failed to establish connection');
      this.scheduleReconnect();
    }
  }

  /**
   * Disconnect from the WebSocket server
   */
  public disconnect(): void {
    this.stopPingInterval();
    
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.websocket) {
      this.websocket.close(1000, 'Client disconnect');
      this.websocket = null;
    }

    this.setConnectionState('disconnected');
  }

  /**
   * Subscribe to specific metric types
   */
  public subscribe(metricTypes: string[], updateInterval = 1.0): void {
    this.subscriptions = metricTypes;
    this.updateInterval = updateInterval;

    if (this.connectionState === 'connected') {
      this.sendMessage({
        type: 'subscribe',
        metric_types: metricTypes,
        update_interval: updateInterval
      });
    }
  }

  /**
   * Unsubscribe from specific metric types
   */
  public unsubscribe(metricTypes?: string[]): void {
    const typesToUnsubscribe = metricTypes || this.subscriptions;
    
    if (typesToUnsubscribe.length > 0 && this.connectionState === 'connected') {
      this.sendMessage({
        type: 'unsubscribe',
        metric_types: typesToUnsubscribe
      });
    }

    if (!metricTypes) {
      // Unsubscribe from all
      this.subscriptions = [];
    } else {
      // Remove specific subscriptions
      this.subscriptions = this.subscriptions.filter(
        sub => !metricTypes.includes(sub)
      );
    }
  }

  /**
   * Request current metrics snapshot
   */
  public requestCurrentMetrics(): void {
    if (this.connectionState === 'connected') {
      this.sendMessage({ type: 'get_current' });
    }
  }

  /**
   * Get current connection state
   */
  public getConnectionState(): ConnectionState {
    return this.connectionState;
  }

  /**
   * Check if connected
   */
  public isConnected(): boolean {
    return this.connectionState === 'connected';
  }

  private setConnectionState(state: ConnectionState): void {
    if (this.connectionState !== state) {
      this.connectionState = state;
      this.onConnectionStateChange?.(state);
    }
  }

  private handleMessage(message: WebSocketMessage): void {
    switch (message.type) {
      case 'connected':
        console.log('Metrics WebSocket connected:', message.message);
        // Re-subscribe if we had active subscriptions
        if (this.subscriptions.length > 0) {
          this.subscribe(this.subscriptions, this.updateInterval);
        }
        break;

      case 'metrics_update':
      case 'live_metrics_update':
        if (message.metrics) {
          this.onMetricsUpdate?.(message.metrics);
        }
        break;

      case 'current_metrics':
        if (message.metrics) {
          this.onMetricsUpdate?.(message.metrics);
        }
        if (message.health_summary) {
          this.onHealthUpdate?.(message.health_summary);
        }
        break;

      case 'health_update':
        if (message.health_summary) {
          this.onHealthUpdate?.(message.health_summary);
        }
        if (message.alerts) {
          message.alerts.forEach((alert: Alert) => {
            this.onAlert?.(alert);
          });
        }
        break;

      case 'subscription_updated':
        console.log('Subscription updated:', message.subscribed_metrics);
        break;

      case 'pong':
        // Pong response to our ping
        break;

      case 'error':
        console.error('Server error:', message.error);
        this.onError?.(message.error);
        break;

      default:
        console.log('Unknown message type:', message.type, message);
        break;
    }
  }

  private sendMessage(message: any): void {
    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
      try {
        this.websocket.send(JSON.stringify(message));
      } catch (error) {
        console.error('Failed to send WebSocket message:', error);
        this.onError?.('Failed to send message to server');
      }
    } else {
      console.warn('Cannot send message: WebSocket not connected');
    }
  }

  private startPingInterval(): void {
    this.stopPingInterval();
    
    this.pingInterval = setInterval(() => {
      if (this.connectionState === 'connected') {
        this.sendMessage({ type: 'ping' });
      }
    }, 30000); // Ping every 30 seconds
  }

  private stopPingInterval(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      this.onError?.('Connection lost and max reconnection attempts exceeded');
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(
      this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
      this.maxReconnectDelay
    );

    console.log(`Scheduling reconnect attempt ${this.reconnectAttempts} in ${delay}ms`);
    
    this.reconnectTimeout = setTimeout(() => {
      console.log(`Reconnect attempt ${this.reconnectAttempts}`);
      this.connect();
    }, delay);
  }
}

/**
 * Create a metrics WebSocket client with default configuration
 */
export function createMetricsWebSocketClient(clientId?: string): MetricsWebSocketClient {
  const id = clientId || `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  const baseUrl = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  const url = `${baseUrl}//${host}/api/system/ws/metrics/${id}`;
  
  return new MetricsWebSocketClient(url);
}

/**
 * Create a system health WebSocket client
 */
export function createHealthWebSocketClient(clientId?: string): MetricsWebSocketClient {
  const id = clientId || `health_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  const baseUrl = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  const url = `${baseUrl}//${host}/api/system/ws/system-health/${id}`;
  
  return new MetricsWebSocketClient(url);
}