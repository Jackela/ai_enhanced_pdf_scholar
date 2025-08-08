/**
 * SecureMessage Component
 * 
 * A security-hardened component for rendering user and AI messages with
 * comprehensive XSS protection, content sanitization, and safe HTML rendering.
 * 
 * @security This component provides XSS-protected message rendering
 * @author AI Enhanced PDF Scholar Security Team
 * @version 2.1.0
 */

import React, { memo } from 'react'
import { clsx } from 'clsx'
import { useChatMessageSecurity, useSecurityMonitoring } from '../../hooks/useSecurity'
import { AlertTriangle, Shield, User, Bot } from 'lucide-react'

interface SecureMessageProps {
  content: string
  role: 'user' | 'assistant'
  timestamp: string | Date
  className?: string
  showSecurityInfo?: boolean
  id?: string | number
}

/**
 * SecureMessage component with XSS protection
 */
export const SecureMessage = memo<SecureMessageProps>(({
  content,
  role,
  timestamp,
  className,
  showSecurityInfo = false,
  id
}) => {
  const { 
    displayContent, 
    shouldRenderAsHTML, 
    hasXSSRisk, 
    xssInfo
  } = useChatMessageSecurity(content, role)
  
  const { logSecurityEvent } = useSecurityMonitoring()

  // Log XSS attempts for monitoring
  React.useEffect(() => {
    if (hasXSSRisk) {
      logSecurityEvent(
        'XSS_ATTEMPT_DETECTED',
        xssInfo.severity,
        {
          messageId: id,
          role,
          patterns: xssInfo.patterns,
          contentPreview: content.substring(0, 100)
        }
      )
    }
  }, [hasXSSRisk, xssInfo, logSecurityEvent, id, role, content])

  const formatTimestamp = (ts: string | Date): string => {
    try {
      const date = ts instanceof Date ? ts : new Date(ts)
      return date.toLocaleTimeString()
    } catch {
      return 'Invalid time'
    }
  }

  const messageClasses = clsx(
    'max-w-sm lg:max-w-md px-4 py-2 rounded-lg relative group',
    {
      // User message styles
      'bg-blue-600 text-white': role === 'user' && !hasXSSRisk,
      'bg-red-600 text-white border-2 border-red-400': role === 'user' && hasXSSRisk,
      
      // Assistant message styles  
      'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white': 
        role === 'assistant' && !hasXSSRisk,
      'bg-red-200 dark:bg-red-900 text-red-900 dark:text-red-100 border-2 border-red-400': 
        role === 'assistant' && hasXSSRisk,
    },
    className
  )

  const containerClasses = clsx(
    'flex items-start gap-2',
    {
      'justify-end': role === 'user',
      'justify-start': role === 'assistant'
    }
  )

  return (
    <div className={containerClasses}>
      {/* Role indicator */}
      {role === 'assistant' && (
        <div className="flex-shrink-0 w-6 h-6 rounded-full bg-green-500 flex items-center justify-center mt-1">
          <Bot size={12} className="text-white" />
        </div>
      )}
      
      <div className={messageClasses}>
        {/* Security warning banner */}
        {hasXSSRisk && (
          <div className="mb-2 p-2 bg-red-100 dark:bg-red-900 rounded border border-red-300 dark:border-red-700">
            <div className="flex items-center gap-2 text-red-700 dark:text-red-300">
              <AlertTriangle size={16} />
              <span className="text-xs font-medium">
                Security Alert: Potentially unsafe content detected
              </span>
            </div>
            {showSecurityInfo && (
              <div className="mt-1 text-xs text-red-600 dark:text-red-400">
                Patterns: {xssInfo.patterns.join(', ')} | Severity: {xssInfo.severity}
              </div>
            )}
          </div>
        )}

        {/* Message content */}
        <div className="message-content">
          {shouldRenderAsHTML && !hasXSSRisk ? (
            <div 
              className="whitespace-pre-wrap prose prose-sm dark:prose-invert max-w-none"
              dangerouslySetInnerHTML={{ __html: displayContent }}
              data-testid="secure-html-content"
            />
          ) : (
            <p 
              className="whitespace-pre-wrap"
              data-testid="secure-text-content"
            >
              {displayContent}
            </p>
          )}
        </div>

        {/* Timestamp and security indicator */}
        <div className="flex items-center justify-between mt-1 text-xs opacity-70">
          <span>
            {formatTimestamp(timestamp)}
          </span>
          
          {/* Security status indicator */}
          <div className="flex items-center gap-1">
            {hasXSSRisk ? (
              <AlertTriangle 
                size={12} 
                className="text-red-400" 
                data-testid="xss-warning-icon"
              />
            ) : (
              <Shield 
                size={12} 
                className="text-green-400" 
                data-testid="secure-content-icon"
              />
            )}
            
            {/* Show content type indicator in development */}
            {process.env.NODE_ENV === 'development' && (
              <span 
                className="text-xs opacity-50"
                title={shouldRenderAsHTML ? 'Rendered as HTML' : 'Rendered as text'}
              >
                {shouldRenderAsHTML ? 'HTML' : 'TEXT'}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Role indicator for user */}
      {role === 'user' && (
        <div className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500 flex items-center justify-center mt-1">
          <User size={12} className="text-white" />
        </div>
      )}
    </div>
  )
})

SecureMessage.displayName = 'SecureMessage'

export default SecureMessage

/**
 * Message List Component with Security Features
 */
interface SecureMessageListProps {
  messages: Array<{
    id: string | number
    role: 'user' | 'assistant'
    content: string
    timestamp: string | Date
  }>
  className?: string
  showSecurityInfo?: boolean
}

export const SecureMessageList = memo<SecureMessageListProps>(({
  messages,
  className,
  showSecurityInfo = false
}) => {
  const { logSecurityEvent } = useSecurityMonitoring()

  // Monitor for bulk XSS attempts
  React.useEffect(() => {
    const xssCount = messages.filter(msg => {
      const { isDetected } = require('../../utils/security').detectXSSAttempt(msg.content)
      return isDetected
    }).length

    if (xssCount > 0) {
      logSecurityEvent(
        'BULK_XSS_DETECTION',
        xssCount > 3 ? 'high' : 'medium',
        { 
          totalMessages: messages.length, 
          xssAttempts: xssCount 
        }
      )
    }
  }, [messages, logSecurityEvent])

  return (
    <div className={clsx('space-y-4', className)}>
      {messages.map((message) => (
        <SecureMessage
          key={message.id}
          id={message.id}
          content={message.content}
          role={message.role}
          timestamp={message.timestamp}
          showSecurityInfo={showSecurityInfo}
        />
      ))}
    </div>
  )
})

SecureMessageList.displayName = 'SecureMessageList'

/**
 * Security Status Component
 */
interface SecurityStatusProps {
  className?: string
}

export const SecurityStatus = memo<SecurityStatusProps>(({ className }) => {
  const { getSecurityEvents } = useSecurityMonitoring()
  const [events, setEvents] = React.useState<any[]>([])

  React.useEffect(() => {
    const interval = setInterval(() => {
      setEvents(getSecurityEvents())
    }, 5000) // Update every 5 seconds

    return () => clearInterval(interval)
  }, [getSecurityEvents])

  const recentEvents = events.slice(-5) // Show last 5 events
  const hasHighSeverityEvents = events.some(e => 
    e.severity === 'high' || e.severity === 'critical'
  )

  if (recentEvents.length === 0) {
    return null
  }

  return (
    <div className={clsx('p-3 rounded-lg border', className, {
      'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800': hasHighSeverityEvents,
      'bg-yellow-50 border-yellow-200 dark:bg-yellow-900/20 dark:border-yellow-800': !hasHighSeverityEvents
    })}>
      <div className="flex items-center gap-2 mb-2">
        <Shield size={16} />
        <h4 className="font-medium text-sm">Security Status</h4>
      </div>
      
      <div className="space-y-1">
        {recentEvents.map((event, index) => (
          <div key={index} className="text-xs opacity-75">
            <span className="font-mono">
              {event.timestamp.toLocaleTimeString()}
            </span>
            <span className="ml-2 capitalize">
              {event.event.replace(/_/g, ' ').toLowerCase()}
            </span>
            <span className={clsx('ml-2 px-1 rounded text-xs', {
              'bg-red-200 text-red-800': event.severity === 'critical',
              'bg-orange-200 text-orange-800': event.severity === 'high',
              'bg-yellow-200 text-yellow-800': event.severity === 'medium',
              'bg-blue-200 text-blue-800': event.severity === 'low'
            })}>
              {event.severity}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
})

SecurityStatus.displayName = 'SecurityStatus'