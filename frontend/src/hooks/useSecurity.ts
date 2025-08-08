/**
 * Security Hooks for XSS Protection
 * 
 * React hooks that provide easy-to-use security utilities for components,
 * including content sanitization, XSS detection, and secure rendering.
 * 
 * @security This module provides React hooks for XSS protection
 * @author AI Enhanced PDF Scholar Security Team
 * @version 2.1.0
 */

import { useMemo, useCallback, useRef, useEffect } from 'react'
import { 
  sanitizeText, 
  sanitizeHTML, 
  sanitizeAndRenderMarkdown,
  detectXSSAttempt,
  escapeHTML,
  SecurityConfig,
  DEFAULT_SECURITY_CONFIG,
  CHAT_SECURITY_CONFIG 
} from '../utils/security'

/**
 * Hook for sanitizing content with memoization for performance
 */
export function useSanitizedContent(
  content: string,
  options: SecurityConfig = DEFAULT_SECURITY_CONFIG
) {
  const sanitizedContent = useMemo(() => {
    if (!content) return ''
    
    if (options.stripAllHTML) {
      return sanitizeText(content)
    }
    
    if (options.allowMarkdown) {
      return sanitizeAndRenderMarkdown(content, options)
    }
    
    return sanitizeHTML(content, options)
  }, [content, options])

  const textContent = useMemo(() => sanitizeText(content), [content])
  
  const isHTML = useMemo(() => 
    content !== textContent && !options.stripAllHTML, 
    [content, textContent, options.stripAllHTML]
  )

  return {
    sanitizedContent,
    textContent,
    isHTML,
    isEmpty: !content || content.trim().length === 0
  }
}

/**
 * Hook for XSS detection and monitoring
 */
export function useXSSDetection(content: string) {
  const detection = useMemo(() => detectXSSAttempt(content), [content])
  
  const logDetection = useCallback((componentName?: string) => {
    if (detection.isDetected) {
      console.warn(`XSS attempt detected${componentName ? ` in ${componentName}` : ''}:`, {
        patterns: detection.patterns,
        severity: detection.severity,
        content: content.substring(0, 100) + (content.length > 100 ? '...' : '')
      })
    }
  }, [detection, content])

  return {
    ...detection,
    logDetection
  }
}

/**
 * Hook for secure input handling with real-time validation
 */
export function useSecureInput(initialValue = '', options: SecurityConfig = DEFAULT_SECURITY_CONFIG) {
  const [value, setValue] = useState(initialValue)
  const [sanitizedValue, setSanitizedValue] = useState('')
  const [hasXSS, setHasXSS] = useState(false)
  const previousValueRef = useRef(initialValue)

  // Sanitize value whenever it changes
  useEffect(() => {
    if (value !== previousValueRef.current) {
      const sanitized = options.stripAllHTML ? sanitizeText(value) : sanitizeHTML(value, options)
      setSanitizedValue(sanitized)
      
      const detection = detectXSSAttempt(value)
      setHasXSS(detection.isDetected)
      
      previousValueRef.current = value
    }
  }, [value, options])

  const handleChange = useCallback((newValue: string) => {
    setValue(newValue)
  }, [])

  const handleSecureSubmit = useCallback((onSubmit: (sanitizedValue: string) => void) => {
    if (!hasXSS) {
      onSubmit(sanitizedValue)
    }
  }, [sanitizedValue, hasXSS])

  return {
    value,
    sanitizedValue,
    hasXSS,
    setValue: handleChange,
    onSecureSubmit: handleSecureSubmit,
    isModified: value !== sanitizedValue
  }
}

/**
 * Hook for safe dangerouslySetInnerHTML usage with XSS protection
 */
export function useSafeInnerHTML(content: string, options: SecurityConfig = DEFAULT_SECURITY_CONFIG) {
  const { sanitizedContent, isHTML } = useSanitizedContent(content, options)
  const xssDetection = useXSSDetection(content)

  const createMarkup = useCallback(() => {
    if (!isHTML || xssDetection.isDetected) {
      return { __html: escapeHTML(content) }
    }
    return { __html: sanitizedContent }
  }, [sanitizedContent, isHTML, xssDetection.isDetected, content])

  // Log XSS attempts for monitoring
  useEffect(() => {
    xssDetection.logDetection('useSafeInnerHTML')
  }, [xssDetection])

  return {
    createMarkup,
    shouldRenderAsHTML: isHTML && !xssDetection.isDetected,
    hasXSSRisk: xssDetection.isDetected,
    xssInfo: xssDetection
  }
}

/**
 * Hook for chat message rendering with appropriate security settings
 */
export function useChatMessageSecurity(message: string, role: 'user' | 'assistant' = 'user') {
  // Users get stricter security, assistants get markdown support
  const securityConfig: SecurityConfig = useMemo(() => {
    if (role === 'assistant') {
      return CHAT_SECURITY_CONFIG
    }
    return {
      ...DEFAULT_SECURITY_CONFIG,
      allowBasicFormatting: true,
      stripAllHTML: false
    }
  }, [role])

  const { sanitizedContent, textContent, isHTML } = useSanitizedContent(message, securityConfig)
  const xssDetection = useXSSDetection(message)

  // For user messages, be more restrictive
  const displayContent = useMemo(() => {
    if (role === 'user' || xssDetection.isDetected) {
      return textContent
    }
    return sanitizedContent
  }, [role, xssDetection.isDetected, textContent, sanitizedContent])

  const shouldRenderAsHTML = useMemo(() => {
    return role === 'assistant' && isHTML && !xssDetection.isDetected
  }, [role, isHTML, xssDetection.isDetected])

  return {
    displayContent,
    shouldRenderAsHTML,
    hasXSSRisk: xssDetection.isDetected,
    xssInfo: xssDetection,
    isFromAssistant: role === 'assistant'
  }
}

/**
 * Hook for content security policy management
 */
export function useContentSecurityPolicy() {
  const applyCSP = useCallback((policy: { [key: string]: string }) => {
    // In a real application, this would communicate with the server
    // to set CSP headers. For client-side applications, we can only
    // suggest security practices.
    console.info('Recommended CSP policy:', policy)
    
    // For development/testing, we can create a meta tag
    if (process.env.NODE_ENV === 'development') {
      const existingCSP = document.querySelector('meta[http-equiv="Content-Security-Policy"]')
      if (existingCSP) {
        existingCSP.remove()
      }
      
      const meta = document.createElement('meta')
      meta.httpEquiv = 'Content-Security-Policy'
      meta.content = Object.entries(policy)
        .map(([directive, value]) => `${directive} ${value}`)
        .join('; ')
      document.head.appendChild(meta)
    }
  }, [])

  return { applyCSP }
}

/**
 * Hook for monitoring security events
 */
export function useSecurityMonitoring() {
  const securityEvents = useRef<{
    timestamp: Date
    event: string
    severity: 'low' | 'medium' | 'high' | 'critical'
    details: any
  }[]>([])

  const logSecurityEvent = useCallback((
    event: string, 
    severity: 'low' | 'medium' | 'high' | 'critical',
    details?: any
  ) => {
    const logEntry = {
      timestamp: new Date(),
      event,
      severity,
      details
    }
    
    securityEvents.current.push(logEntry)
    
    // Keep only last 100 events to prevent memory leaks
    if (securityEvents.current.length > 100) {
      securityEvents.current = securityEvents.current.slice(-100)
    }
    
    // Log to console based on severity
    if (severity === 'critical' || severity === 'high') {
      console.error('Security Event:', logEntry)
    } else if (severity === 'medium') {
      console.warn('Security Event:', logEntry)
    } else {
      console.info('Security Event:', logEntry)
    }
  }, [])

  const getSecurityEvents = useCallback(() => [...securityEvents.current], [])
  
  const clearSecurityEvents = useCallback(() => {
    securityEvents.current = []
  }, [])

  return {
    logSecurityEvent,
    getSecurityEvents,
    clearSecurityEvents
  }
}

// Import useState for useSecureInput
import { useState } from 'react'