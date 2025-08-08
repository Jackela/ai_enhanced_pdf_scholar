/**
 * Security Hooks Tests
 * 
 * Test suite for React security hooks including content sanitization,
 * XSS detection, and secure input handling.
 * 
 * @security Tests React hooks for XSS protection
 * @author AI Enhanced PDF Scholar Security Team
 * @version 2.1.0
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import {
  useSanitizedContent,
  useXSSDetection,
  useSecureInput,
  useSafeInnerHTML,
  useChatMessageSecurity,
  useSecurityMonitoring
} from '../hooks/useSecurity'
import { DEFAULT_SECURITY_CONFIG } from '../utils/security'

// Mock console methods for testing
const mockConsole = {
  warn: vi.fn(),
  error: vi.fn(),
  info: vi.fn()
}

beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(mockConsole.warn)
  vi.spyOn(console, 'error').mockImplementation(mockConsole.error)
  vi.spyOn(console, 'info').mockImplementation(mockConsole.info)
})

afterEach(() => {
  vi.restoreAllMocks()
  mockConsole.warn.mockClear()
  mockConsole.error.mockClear()
  mockConsole.info.mockClear()
})

describe('useSanitizedContent', () => {
  it('should sanitize basic HTML content', () => {
    const { result } = renderHook(() => 
      useSanitizedContent('<p>Hello <strong>World</strong></p>', DEFAULT_SECURITY_CONFIG)
    )

    expect(result.current.sanitizedContent).toContain('<p>')
    expect(result.current.sanitizedContent).toContain('<strong>')
    expect(result.current.textContent).toBe('Hello World')
    expect(result.current.isHTML).toBe(true)
    expect(result.current.isEmpty).toBe(false)
  })

  it('should handle XSS attempts', () => {
    const maliciousContent = '<script>alert("XSS")</script><p>Safe content</p>'
    const { result } = renderHook(() => 
      useSanitizedContent(maliciousContent, DEFAULT_SECURITY_CONFIG)
    )

    expect(result.current.sanitizedContent).not.toContain('<script>')
    expect(result.current.sanitizedContent).not.toContain('alert')
    expect(result.current.sanitizedContent).toContain('<p>')
    expect(result.current.textContent).toBe('alert("XSS")Safe content')
  })

  it('should handle markdown when enabled', () => {
    const markdown = '# Title\n\n**Bold text**'
    const { result } = renderHook(() => 
      useSanitizedContent(markdown, { ...DEFAULT_SECURITY_CONFIG, allowMarkdown: true })
    )

    expect(result.current.sanitizedContent).toContain('<h1>')
    expect(result.current.sanitizedContent).toContain('<strong>')
  })

  it('should strip all HTML when configured', () => {
    const htmlContent = '<p>Hello <strong>World</strong></p>'
    const { result } = renderHook(() => 
      useSanitizedContent(htmlContent, { stripAllHTML: true })
    )

    expect(result.current.sanitizedContent).toBe('Hello World')
    expect(result.current.isHTML).toBe(false)
  })

  it('should handle empty content', () => {
    const { result } = renderHook(() => 
      useSanitizedContent('', DEFAULT_SECURITY_CONFIG)
    )

    expect(result.current.isEmpty).toBe(true)
    expect(result.current.sanitizedContent).toBe('')
  })

  it('should memoize results for performance', () => {
    const content = '<p>Test content</p>'
    const { result, rerender } = renderHook(
      ({ content, config }) => useSanitizedContent(content, config),
      { initialProps: { content, config: DEFAULT_SECURITY_CONFIG } }
    )

    const firstResult = result.current.sanitizedContent

    // Rerender with same props
    rerender({ content, config: DEFAULT_SECURITY_CONFIG })
    expect(result.current.sanitizedContent).toBe(firstResult)

    // Rerender with different content
    rerender({ content: '<p>New content</p>', config: DEFAULT_SECURITY_CONFIG })
    expect(result.current.sanitizedContent).not.toBe(firstResult)
  })
})

describe('useXSSDetection', () => {
  it('should detect script injection', () => {
    const { result } = renderHook(() => 
      useXSSDetection('<script>alert("XSS")</script>')
    )

    expect(result.current.isDetected).toBe(true)
    expect(result.current.severity).toBe('critical')
    expect(result.current.patterns).toContain('Script Tags')
  })

  it('should detect JavaScript URLs', () => {
    const { result } = renderHook(() => 
      useXSSDetection('javascript:alert("XSS")')
    )

    expect(result.current.isDetected).toBe(true)
    expect(result.current.severity).toBe('critical')
    expect(result.current.patterns).toContain('JavaScript URLs')
  })

  it('should not detect safe content', () => {
    const { result } = renderHook(() => 
      useXSSDetection('This is safe content')
    )

    expect(result.current.isDetected).toBe(false)
    expect(result.current.severity).toBe('low')
    expect(result.current.patterns).toHaveLength(0)
  })

  it('should log detection when called', () => {
    const { result } = renderHook(() => 
      useXSSDetection('<script>alert("XSS")</script>')
    )

    act(() => {
      result.current.logDetection('TestComponent')
    })

    expect(mockConsole.warn).toHaveBeenCalledWith(
      expect.stringContaining('XSS attempt detected in TestComponent'),
      expect.any(Object)
    )
  })

  it('should not log for safe content', () => {
    const { result } = renderHook(() => 
      useXSSDetection('Safe content')
    )

    act(() => {
      result.current.logDetection()
    })

    expect(mockConsole.warn).not.toHaveBeenCalled()
  })
})

describe('useSecureInput', () => {
  it('should initialize with safe value', () => {
    const { result } = renderHook(() => 
      useSecureInput('Initial value', DEFAULT_SECURITY_CONFIG)
    )

    expect(result.current.value).toBe('Initial value')
    expect(result.current.sanitizedValue).toBe('Initial value')
    expect(result.current.hasXSS).toBe(false)
    expect(result.current.isModified).toBe(false)
  })

  it('should handle XSS input', () => {
    const { result } = renderHook(() => 
      useSecureInput('', DEFAULT_SECURITY_CONFIG)
    )

    act(() => {
      result.current.setValue('<script>alert("XSS")</script>')
    })

    expect(result.current.value).toBe('<script>alert("XSS")</script>')
    expect(result.current.hasXSS).toBe(true)
    expect(result.current.sanitizedValue).not.toContain('<script>')
    expect(result.current.isModified).toBe(true)
  })

  it('should prevent submission with XSS', () => {
    const mockSubmit = vi.fn()
    const { result } = renderHook(() => 
      useSecureInput('', DEFAULT_SECURITY_CONFIG)
    )

    act(() => {
      result.current.setValue('<script>alert("XSS")</script>')
    })

    act(() => {
      result.current.onSecureSubmit(mockSubmit)
    })

    expect(mockSubmit).not.toHaveBeenCalled()
  })

  it('should allow submission with safe content', () => {
    const mockSubmit = vi.fn()
    const { result } = renderHook(() => 
      useSecureInput('', DEFAULT_SECURITY_CONFIG)
    )

    act(() => {
      result.current.setValue('Safe content')
    })

    act(() => {
      result.current.onSecureSubmit(mockSubmit)
    })

    expect(mockSubmit).toHaveBeenCalledWith('Safe content')
  })
})

describe('useSafeInnerHTML', () => {
  it('should create safe markup for HTML content', () => {
    const { result } = renderHook(() => 
      useSafeInnerHTML('<p>Safe <strong>HTML</strong></p>', DEFAULT_SECURITY_CONFIG)
    )

    expect(result.current.shouldRenderAsHTML).toBe(true)
    expect(result.current.hasXSSRisk).toBe(false)
    expect(result.current.createMarkup().__html).toContain('<p>')
  })

  it('should escape dangerous content', () => {
    const { result } = renderHook(() => 
      useSafeInnerHTML('<script>alert("XSS")</script>', DEFAULT_SECURITY_CONFIG)
    )

    expect(result.current.shouldRenderAsHTML).toBe(false)
    expect(result.current.hasXSSRisk).toBe(true)
    expect(result.current.createMarkup().__html).toContain('&lt;script&gt;')
  })

  it('should log XSS attempts', () => {
    renderHook(() => 
      useSafeInnerHTML('<script>alert("XSS")</script>', DEFAULT_SECURITY_CONFIG)
    )

    expect(mockConsole.warn).toHaveBeenCalled()
  })
})

describe('useChatMessageSecurity', () => {
  it('should handle user messages with strict security', () => {
    const { result } = renderHook(() => 
      useChatMessageSecurity('Hello <strong>World</strong>', 'user')
    )

    expect(result.current.isFromAssistant).toBe(false)
    expect(result.current.shouldRenderAsHTML).toBe(false)
    // User content should be text-only for security
    expect(result.current.displayContent).toBe('Hello World')
  })

  it('should handle assistant messages with markdown support', () => {
    const { result } = renderHook(() => 
      useChatMessageSecurity('**Bold text** and `code`', 'assistant')
    )

    expect(result.current.isFromAssistant).toBe(true)
    expect(result.current.shouldRenderAsHTML).toBe(true)
    expect(result.current.displayContent).toContain('<strong>')
    expect(result.current.displayContent).toContain('<code>')
  })

  it('should block XSS in assistant messages', () => {
    const { result } = renderHook(() => 
      useChatMessageSecurity('<script>alert("XSS")</script>Safe content', 'assistant')
    )

    expect(result.current.hasXSSRisk).toBe(true)
    expect(result.current.shouldRenderAsHTML).toBe(false)
    expect(result.current.displayContent).toBe('alert("XSS")Safe content')
  })

  it('should use appropriate security configs', () => {
    const userResult = renderHook(() => 
      useChatMessageSecurity('Test', 'user')
    ).result

    const assistantResult = renderHook(() => 
      useChatMessageSecurity('Test', 'assistant')
    ).result

    expect(userResult.current.isFromAssistant).toBe(false)
    expect(assistantResult.current.isFromAssistant).toBe(true)
  })
})

describe('useSecurityMonitoring', () => {
  it('should log security events', () => {
    const { result } = renderHook(() => useSecurityMonitoring())

    act(() => {
      result.current.logSecurityEvent('TEST_EVENT', 'high', { test: 'data' })
    })

    expect(mockConsole.error).toHaveBeenCalledWith(
      'Security Event:',
      expect.objectContaining({
        event: 'TEST_EVENT',
        severity: 'high',
        details: { test: 'data' }
      })
    )

    const events = result.current.getSecurityEvents()
    expect(events).toHaveLength(1)
    expect(events[0].event).toBe('TEST_EVENT')
  })

  it('should limit event history', () => {
    const { result } = renderHook(() => useSecurityMonitoring())

    // Log 105 events (should keep only last 100)
    act(() => {
      for (let i = 0; i < 105; i++) {
        result.current.logSecurityEvent(`EVENT_${i}`, 'low')
      }
    })

    const events = result.current.getSecurityEvents()
    expect(events).toHaveLength(100)
    expect(events[0].event).toBe('EVENT_5') // First 5 should be dropped
  })

  it('should clear events', () => {
    const { result } = renderHook(() => useSecurityMonitoring())

    act(() => {
      result.current.logSecurityEvent('TEST_EVENT', 'low')
    })

    expect(result.current.getSecurityEvents()).toHaveLength(1)

    act(() => {
      result.current.clearSecurityEvents()
    })

    expect(result.current.getSecurityEvents()).toHaveLength(0)
  })

  it('should use appropriate log levels', () => {
    const { result } = renderHook(() => useSecurityMonitoring())

    act(() => {
      result.current.logSecurityEvent('CRITICAL_EVENT', 'critical')
      result.current.logSecurityEvent('HIGH_EVENT', 'high')
      result.current.logSecurityEvent('MEDIUM_EVENT', 'medium')
      result.current.logSecurityEvent('LOW_EVENT', 'low')
    })

    expect(mockConsole.error).toHaveBeenCalledTimes(2) // critical + high
    expect(mockConsole.warn).toHaveBeenCalledTimes(1)  // medium
    expect(mockConsole.info).toHaveBeenCalledTimes(1)  // low
  })
})

describe('Hook Integration Tests', () => {
  it('should work together for complete security', () => {
    const maliciousInput = '<script>alert("XSS")</script>Safe content'
    
    // Test detection
    const { result: detectionResult } = renderHook(() => 
      useXSSDetection(maliciousInput)
    )

    // Test sanitization
    const { result: sanitizationResult } = renderHook(() => 
      useSanitizedContent(maliciousInput, DEFAULT_SECURITY_CONFIG)
    )

    // Test secure input
    const { result: inputResult } = renderHook(() => 
      useSecureInput('', DEFAULT_SECURITY_CONFIG)
    )

    // Test monitoring
    renderHook(() => 
      useSecurityMonitoring()
    )

    expect(detectionResult.current.isDetected).toBe(true)
    expect(sanitizationResult.current.sanitizedContent).not.toContain('<script>')
    
    act(() => {
      inputResult.current.setValue(maliciousInput)
    })
    
    expect(inputResult.current.hasXSS).toBe(true)
    
    act(() => {
      detectionResult.current.logDetection('IntegrationTest')
    })
    
    expect(mockConsole.warn).toHaveBeenCalled()
  })

  it('should handle real-world chat scenario', () => {
    // Simulate a chat interaction with various security concerns
    const messages = [
      { content: 'Hello!', role: 'user' as const },
      { content: '**Hello!** How can I help?', role: 'assistant' as const },
      { content: '<script>alert("hack")</script>How about this?', role: 'user' as const }
    ]

    const results = messages.map(msg => 
      renderHook(() => useChatMessageSecurity(msg.content, msg.role)).result.current
    )

    // First message (user, safe)
    expect(results[0].hasXSSRisk).toBe(false)
    expect(results[0].shouldRenderAsHTML).toBe(false)

    // Second message (assistant, markdown)
    expect(results[1].hasXSSRisk).toBe(false)
    expect(results[1].shouldRenderAsHTML).toBe(true)
    expect(results[1].displayContent).toContain('<strong>')

    // Third message (user, XSS attempt)
    expect(results[2].hasXSSRisk).toBe(true)
    expect(results[2].shouldRenderAsHTML).toBe(false)
    expect(results[2].displayContent).not.toContain('<script>')
  })
})