/**
 * Alerts Panel Component
 * 
 * Displays system alerts and notifications with severity levels,
 * timestamps, and actionable information.
 */

import React, { useState } from 'react';
import { 
  Bell, 
  AlertTriangle, 
  AlertCircle, 
  Info, 
  X, 
  Clock,
  ChevronDown,
  ChevronUp,
  Filter
} from 'lucide-react';
import { Button } from '../ui/Button';

interface Alert {
  type: string;
  severity: 'info' | 'warning' | 'error' | 'critical';
  message: string;
  timestamp: string;
  value?: number;
  threshold?: number;
}

interface AlertsPanelProps {
  alerts: Alert[];
  onDismissAlert?: (index: number) => void;
  onClearAll?: () => void;
}

type SeverityFilter = 'all' | 'info' | 'warning' | 'error' | 'critical';

export const AlertsPanel: React.FC<AlertsPanelProps> = ({ 
  alerts, 
  onDismissAlert,
  onClearAll 
}) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>('all');
  const [showDetails, setShowDetails] = useState<Record<number, boolean>>({});

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical':
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      case 'error':
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      case 'warning':
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      case 'info':
        return <Info className="h-4 w-4 text-blue-500" />;
      default:
        return <Bell className="h-4 w-4 text-gray-500" />;
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'bg-red-100 border-red-300 text-red-800';
      case 'error':
        return 'bg-red-50 border-red-200 text-red-700';
      case 'warning':
        return 'bg-yellow-50 border-yellow-200 text-yellow-700';
      case 'info':
        return 'bg-blue-50 border-blue-200 text-blue-700';
      default:
        return 'bg-gray-50 border-gray-200 text-gray-700';
    }
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'bg-red-600 text-white';
      case 'error':
        return 'bg-red-500 text-white';
      case 'warning':
        return 'bg-yellow-500 text-white';
      case 'info':
        return 'bg-blue-500 text-white';
      default:
        return 'bg-gray-500 text-white';
    }
  };

  const formatTimestamp = (timestamp: string): string => {
    try {
      const date = new Date(timestamp);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffSeconds = Math.floor(diffMs / 1000);
      const diffMinutes = Math.floor(diffSeconds / 60);
      const diffHours = Math.floor(diffMinutes / 60);

      if (diffSeconds < 60) {
        return `${diffSeconds}s ago`;
      } else if (diffMinutes < 60) {
        return `${diffMinutes}m ago`;
      } else if (diffHours < 24) {
        return `${diffHours}h ago`;
      } else {
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
      }
    } catch (error) {
      return timestamp;
    }
  };

  const filteredAlerts = alerts.filter(alert => 
    severityFilter === 'all' || alert.severity === severityFilter
  );

  const criticalCount = alerts.filter(alert => alert.severity === 'critical').length;
  const errorCount = alerts.filter(alert => alert.severity === 'error').length;
  const warningCount = alerts.filter(alert => alert.severity === 'warning').length;
  const infoCount = alerts.filter(alert => alert.severity === 'info').length;

  const toggleDetails = (index: number) => {
    setShowDetails(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  return (
    <div className="bg-white rounded-lg shadow">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <div className="flex items-center space-x-2">
          <Bell className="h-5 w-5 text-orange-500" />
          <h3 className="font-semibold text-gray-900">System Alerts</h3>
          {alerts.length > 0 && (
            <span className="bg-red-100 text-red-800 text-xs font-medium px-2 py-1 rounded-full">
              {alerts.length}
            </span>
          )}
        </div>
        
        <div className="flex items-center space-x-2">
          {/* Severity Filter */}
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value as SeverityFilter)}
            className="text-xs border border-gray-300 rounded px-2 py-1"
          >
            <option value="all">All ({alerts.length})</option>
            <option value="critical">Critical ({criticalCount})</option>
            <option value="error">Error ({errorCount})</option>
            <option value="warning">Warning ({warningCount})</option>
            <option value="info">Info ({infoCount})</option>
          </select>

          {/* Clear All Button */}
          {alerts.length > 0 && onClearAll && (
            <Button
              onClick={onClearAll}
              variant="outline"
              size="sm"
              className="text-xs"
            >
              Clear All
            </Button>
          )}

          {/* Expand/Collapse */}
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-gray-500 hover:text-gray-700"
          >
            {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Content */}
      {isExpanded && (
        <div className="max-h-96 overflow-y-auto">
          {filteredAlerts.length === 0 ? (
            <div className="text-center text-gray-500 py-8">
              <Bell className="h-12 w-12 mx-auto mb-2 opacity-50" />
              <p>No alerts to display</p>
              <p className="text-sm mt-1">
                {alerts.length > 0 ? 
                  `No ${severityFilter} alerts` : 
                  'System is running smoothly'
                }
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {filteredAlerts.map((alert, index) => (
                <div
                  key={`${alert.timestamp}-${index}`}
                  className={`p-4 border-l-4 ${
                    alert.severity === 'critical' ? 'border-red-500' :
                    alert.severity === 'error' ? 'border-red-400' :
                    alert.severity === 'warning' ? 'border-yellow-400' :
                    'border-blue-400'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start space-x-3 flex-1">
                      {getSeverityIcon(alert.severity)}
                      
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center space-x-2 mb-1">
                          <span className={`text-xs font-medium px-2 py-1 rounded ${getSeverityBadge(alert.severity)}`}>
                            {alert.severity.toUpperCase()}
                          </span>
                          <span className="text-xs text-gray-500 capitalize">
                            {alert.type.replace('_', ' ')}
                          </span>
                        </div>
                        
                        <p className="text-sm text-gray-900 mb-2">
                          {alert.message}
                        </p>
                        
                        <div className="flex items-center space-x-4 text-xs text-gray-500">
                          <div className="flex items-center space-x-1">
                            <Clock className="h-3 w-3" />
                            <span>{formatTimestamp(alert.timestamp)}</span>
                          </div>
                          
                          {alert.value !== undefined && alert.threshold !== undefined && (
                            <div>
                              Value: {alert.value} / Threshold: {alert.threshold}
                            </div>
                          )}
                        </div>

                        {/* Additional Details */}
                        {showDetails[index] && (
                          <div className="mt-3 p-2 bg-gray-50 rounded text-xs">
                            <div className="grid grid-cols-2 gap-2">
                              <div>
                                <span className="font-medium">Type:</span> {alert.type}
                              </div>
                              <div>
                                <span className="font-medium">Severity:</span> {alert.severity}
                              </div>
                              {alert.value !== undefined && (
                                <div>
                                  <span className="font-medium">Current Value:</span> {alert.value}
                                </div>
                              )}
                              {alert.threshold !== undefined && (
                                <div>
                                  <span className="font-medium">Threshold:</span> {alert.threshold}
                                </div>
                              )}
                            </div>
                            <div className="mt-2">
                              <span className="font-medium">Timestamp:</span> {alert.timestamp}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center space-x-1 ml-2">
                      {/* Details Toggle */}
                      <button
                        onClick={() => toggleDetails(index)}
                        className="text-gray-400 hover:text-gray-600 p-1"
                        title="Toggle details"
                      >
                        {showDetails[index] ? (
                          <ChevronUp className="h-4 w-4" />
                        ) : (
                          <ChevronDown className="h-4 w-4" />
                        )}
                      </button>

                      {/* Dismiss Button */}
                      {onDismissAlert && (
                        <button
                          onClick={() => onDismissAlert(index)}
                          className="text-gray-400 hover:text-gray-600 p-1"
                          title="Dismiss alert"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Footer Stats */}
      {alerts.length > 0 && (
        <div className="px-4 py-2 bg-gray-50 border-t border-gray-200 text-xs text-gray-600">
          <div className="flex justify-between items-center">
            <div className="flex space-x-4">
              {criticalCount > 0 && (
                <span className="text-red-600 font-medium">
                  {criticalCount} Critical
                </span>
              )}
              {errorCount > 0 && (
                <span className="text-red-500">
                  {errorCount} Error
                </span>
              )}
              {warningCount > 0 && (
                <span className="text-yellow-600">
                  {warningCount} Warning
                </span>
              )}
              {infoCount > 0 && (
                <span className="text-blue-600">
                  {infoCount} Info
                </span>
              )}
            </div>
            <div>
              Showing {filteredAlerts.length} of {alerts.length} alerts
            </div>
          </div>
        </div>
      )}
    </div>
  );
};