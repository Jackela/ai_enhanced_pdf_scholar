/**
 * SecureMarkdown Component
 * 
 * A security-hardened markdown renderer with XSS protection, content sanitization,
 * and safe HTML rendering using DOMPurify and marked.
 * 
 * @security Provides XSS-protected markdown rendering
 * @author AI Enhanced PDF Scholar Security Team
 * @version 2.1.0
 */

import React, { memo, useMemo } from 'react'
import { clsx } from 'clsx'
import { sanitizeAndRenderMarkdown, detectXSSAttempt, SecurityConfig, CHAT_SECURITY_CONFIG } from '../../utils/security'
import { useSecurityMonitoring } from '../../hooks/useSecurity'
import { AlertTriangle, Shield, FileText } from 'lucide-react'

interface SecureMarkdownProps {
  content: string
  className?: string
  securityConfig?: SecurityConfig
  showSecurityInfo?: boolean
  onXSSDetected?: (info: { patterns: string[]; severity: string }) => void
  allowImages?: boolean
  allowLinks?: boolean
  allowCodeBlocks?: boolean
  allowTables?: boolean
  maxLength?: number
  componentId?: string
}

/**
 * SecureMarkdown component with XSS protection
 */
export const SecureMarkdown = memo<SecureMarkdownProps>(({
  content,
  className,
  securityConfig = CHAT_SECURITY_CONFIG,
  showSecurityInfo = false,
  onXSSDetected,
  allowImages = false,
  allowLinks = true,
  allowCodeBlocks = true,
  allowTables = true,
  maxLength = 50000,
  componentId = 'SecureMarkdown'
}) => {
  const { logSecurityEvent } = useSecurityMonitoring()

  // Truncate content if too long
  const truncatedContent = useMemo(() => {
    if (content.length > maxLength) {
      logSecurityEvent('CONTENT_TRUNCATED', 'low', { 
        originalLength: content.length, 
        maxLength,
        componentId 
      })
      return content.substring(0, maxLength) + '\n\n*[Content truncated for security]*'
    }
    return content
  }, [content, maxLength, logSecurityEvent, componentId])

  // XSS Detection
  const xssDetection = useMemo(() => detectXSSAttempt(truncatedContent), [truncatedContent])

  // Security configuration with props override
  const finalSecurityConfig = useMemo(() => ({
    ...securityConfig,
    allowImages,
    allowLinks,
    allowCodeBlocks,
    allowTables,
    allowMarkdown: true
  }), [securityConfig, allowImages, allowLinks, allowCodeBlocks, allowTables])

  // Sanitized HTML content
  const sanitizedHTML = useMemo(() => {
    try {
      return sanitizeAndRenderMarkdown(truncatedContent, finalSecurityConfig)
    } catch (error) {
      console.error('Markdown rendering error:', error)
      logSecurityEvent('MARKDOWN_RENDER_ERROR', 'medium', { 
        error: error instanceof Error ? error.message : 'Unknown error',
        componentId 
      })
      return '<p>Error rendering markdown content</p>'
    }
  }, [truncatedContent, finalSecurityConfig, logSecurityEvent, componentId])

  // Log XSS detection
  React.useEffect(() => {
    if (xssDetection.isDetected) {
      logSecurityEvent('XSS_MARKDOWN_DETECTED', xssDetection.severity, {
        patterns: xssDetection.patterns,
        componentId,
        contentPreview: truncatedContent.substring(0, 100)
      })
      
      if (onXSSDetected) {
        onXSSDetected({
          patterns: xssDetection.patterns,
          severity: xssDetection.severity
        })
      }
    }
  }, [xssDetection, logSecurityEvent, componentId, truncatedContent, onXSSDetected])

  const containerClasses = clsx(
    'secure-markdown prose prose-sm dark:prose-invert max-w-none',
    {
      'border-2 border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-900/20 p-3 rounded': 
        xssDetection.isDetected,
    },
    className
  )

  if (!content.trim()) {
    return (
      <div className="text-gray-500 dark:text-gray-400 italic text-sm">
        <FileText size={16} className="inline mr-1" />
        No content to display
      </div>
    )
  }

  return (
    <div className="secure-markdown-container">
      {/* Security warning banner */}
      {xssDetection.isDetected && (
        <div className="mb-3 p-3 bg-red-100 dark:bg-red-900 rounded border border-red-300 dark:border-red-700">
          <div className="flex items-center gap-2 text-red-700 dark:text-red-300 mb-1">
            <AlertTriangle size={16} />
            <span className="font-medium text-sm">
              Potentially unsafe content detected in markdown
            </span>
          </div>
          {showSecurityInfo && (
            <div className="text-xs text-red-600 dark:text-red-400">
              <div>Patterns: {xssDetection.patterns.join(', ')}</div>
              <div>Severity: {xssDetection.severity}</div>
              <div>The content has been sanitized before rendering.</div>
            </div>
          )}
        </div>
      )}

      {/* Rendered markdown content */}
      <div 
        className={containerClasses}
        dangerouslySetInnerHTML={{ __html: sanitizedHTML }}
        data-testid="secure-markdown-content"
        data-has-xss={xssDetection.isDetected}
        data-component-id={componentId}
      />

      {/* Security footer */}
      {showSecurityInfo && (
        <div className="mt-2 flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
          <div className="flex items-center gap-1">
            <Shield size={12} />
            <span>Markdown rendered securely</span>
          </div>
          <div className="flex items-center gap-2">
            {xssDetection.isDetected ? (
              <span className="text-red-500">⚠ Content sanitized</span>
            ) : (
              <span className="text-green-500">✓ Content safe</span>
            )}
            {process.env.NODE_ENV === 'development' && (
              <span className="opacity-50">
                Config: {Object.entries(finalSecurityConfig)
                  .filter(([_, value]) => value === true)
                  .map(([key]) => key.replace('allow', ''))
                  .join(', ')}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  )
})

SecureMarkdown.displayName = 'SecureMarkdown'

/**
 * SecureMarkdownPreview - Read-only preview with enhanced security
 */
interface SecureMarkdownPreviewProps extends Omit<SecureMarkdownProps, 'onXSSDetected'> {
  title?: string
  collapsible?: boolean
  maxPreviewLength?: number
}

export const SecureMarkdownPreview = memo<SecureMarkdownPreviewProps>(({
  content,
  title,
  collapsible = false,
  maxPreviewLength = 200,
  className,
  ...otherProps
}) => {
  const [isExpanded, setIsExpanded] = React.useState(!collapsible)
  const { logSecurityEvent } = useSecurityMonitoring()

  const previewContent = useMemo(() => {
    if (!collapsible || isExpanded) {
      return content
    }
    
    const truncated = content.length > maxPreviewLength
    const preview = truncated ? content.substring(0, maxPreviewLength) + '...' : content
    
    if (truncated) {
      logSecurityEvent('MARKDOWN_PREVIEW_TRUNCATED', 'low', { 
        originalLength: content.length,
        previewLength: maxPreviewLength 
      })
    }
    
    return preview
  }, [content, collapsible, isExpanded, maxPreviewLength, logSecurityEvent])

  return (
    <div className={clsx('secure-markdown-preview', className)}>
      {title && (
        <div className="flex items-center justify-between mb-2">
          <h4 className="font-medium text-sm text-gray-900 dark:text-white">
            {title}
          </h4>
          {collapsible && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="text-xs text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-200"
              aria-label={isExpanded ? 'Collapse content' : 'Expand content'}
            >
              {isExpanded ? 'Collapse' : 'Expand'}
            </button>
          )}
        </div>
      )}
      
      <SecureMarkdown
        content={previewContent}
        {...otherProps}
        className={clsx('text-sm', className)}
      />
      
      {collapsible && !isExpanded && content.length > maxPreviewLength && (
        <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
          Content truncated ({content.length - maxPreviewLength} more characters)
        </div>
      )}
    </div>
  )
})

SecureMarkdownPreview.displayName = 'SecureMarkdownPreview'

/**
 * SecureCodeBlock - Enhanced code block with syntax highlighting protection
 */
interface SecureCodeBlockProps {
  code: string
  language?: string
  filename?: string
  showLineNumbers?: boolean
  maxLines?: number
  className?: string
}

export const SecureCodeBlock = memo<SecureCodeBlockProps>(({
  code,
  language = 'text',
  filename,
  showLineNumbers = false,
  maxLines = 100,
  className
}) => {
  const { logSecurityEvent } = useSecurityMonitoring()

  const sanitizedCode = useMemo(() => {
    // Remove potentially dangerous content from code blocks
    let cleanCode = code
      .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '// [script tag removed]')
      .replace(/javascript:/gi, '// javascript: protocol removed')
      .replace(/vbscript:/gi, '// vbscript: protocol removed')
      .replace(/data:/gi, '// data: protocol removed')

    // Limit line count
    const lines = cleanCode.split('\n')
    if (lines.length > maxLines) {
      logSecurityEvent('CODE_BLOCK_TRUNCATED', 'low', { 
        originalLines: lines.length,
        maxLines,
        language 
      })
      cleanCode = lines.slice(0, maxLines).join('\n') + '\n// [Code truncated for security]'
    }

    return cleanCode
  }, [code, maxLines, logSecurityEvent, language])

  const xssDetection = useMemo(() => detectXSSAttempt(code), [code])

  React.useEffect(() => {
    if (xssDetection.isDetected) {
      logSecurityEvent('XSS_CODE_BLOCK_DETECTED', xssDetection.severity, {
        patterns: xssDetection.patterns,
        language,
        filename
      })
    }
  }, [xssDetection, logSecurityEvent, language, filename])

  return (
    <div className={clsx('secure-code-block', className)}>
      {filename && (
        <div className="bg-gray-100 dark:bg-gray-800 px-3 py-1 text-xs font-mono border-b border-gray-200 dark:border-gray-700">
          {filename}
          {xssDetection.isDetected && (
            <span className="ml-2 text-red-500">⚠ Content sanitized</span>
          )}
        </div>
      )}
      
      <pre className="bg-gray-50 dark:bg-gray-900 p-3 rounded-b overflow-x-auto text-sm">
        <code 
          className={`language-${language}`}
          data-testid="secure-code-content"
        >
          {showLineNumbers ? (
            sanitizedCode.split('\n').map((line, i) => (
              <div key={i} className="flex">
                <span className="text-gray-400 mr-3 select-none">
                  {(i + 1).toString().padStart(3, ' ')}
                </span>
                <span>{line}</span>
              </div>
            ))
          ) : (
            sanitizedCode
          )}
        </code>
      </pre>
      
      {xssDetection.isDetected && (
        <div className="mt-1 text-xs text-red-600 dark:text-red-400 flex items-center gap-1">
          <AlertTriangle size={12} />
          Potentially unsafe content was sanitized in this code block.
        </div>
      )}
    </div>
  )
})

SecureCodeBlock.displayName = 'SecureCodeBlock'

export default SecureMarkdown