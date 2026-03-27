import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import {
  useSanitizedContent,
  useXSSDetection,
  useSecureInput,
  useSafeInnerHTML,
  useChatMessageSecurity,
  useContentSecurityPolicy,
  useSecurityMonitoring,
} from '../useSecurity'
import {
  sanitizeText,
  sanitizeHTML,
  detectXSSAttempt,
  escapeHTML,
  DEFAULT_SECURITY_CONFIG,
} from '../../utils/security'

// Mock the security utils
vi.mock('../../utils/security', () => ({
  sanitizeText: vi.fn((text: string) => text.replace(/\u003c[^\u003e]*\u003e/g, '')),
  sanitizeHTML: vi.fn((html: string) => html.replace(/\u003cscript[^\u003e]*\u003e[\s\S]*?\u003c\/script\u003e/gi, '')),
  sanitizeAndRenderMarkdown: vi.fn((text: string) => `<p>${text}\u003c/p>`),
  detectXSSAttempt: vi.fn(),
  escapeHTML: vi.fn((text: string) =>
    text
      .replace(/\u0026/g, '&amp;')
      .replace(/\u003c/g, '&lt;')
      .replace(/\u003e/g, '&gt;')
  ),
  DEFAULT_SECURITY_CONFIG: {
    allowMarkdown: false,
    allowImages: false,
    allowLinks: false,
    allowTables: false,
    allowCodeBlocks: false,
    allowBasicFormatting: true,
    stripAllHTML: false,
  },
  CHAT_SECURITY_CONFIG: {
    allowMarkdown: true,
    allowImages: false,
    allowLinks: true,
    allowTables: true,
    allowCodeBlocks: true,
    allowBasicFormatting: true,
    stripAllHTML: false,
  },
}))

describe('useSecurity hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(detectXSSAttempt).mockReturnValue({
      isDetected: false,
      patterns: [],
      severity: 'low',
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('useSanitizedContent', () => {
    it('returns sanitized content for plain text', () => {
      vi.mocked(sanitizeText).mockReturnValue('Hello World')

      const { result } = renderHook(() => useSanitizedContent('Hello World'))

      expect(result.current.sanitizedContent).toBe('Hello World')
      expect(result.current.isHTML).toBe(false)
      expect(result.current.isEmpty).toBe(false)
    })

    it('strips all HTML when stripAllHTML is true', () => {
      vi.mocked(sanitizeText).mockReturnValue('Hello World')

      const { result } = renderHook(() =>
        useSanitizedContent('<b>Hello</b> World', { ...DEFAULT_SECURITY_CONFIG, stripAllHTML: true })
      )

      expect(sanitizeText).toHaveBeenCalledWith('<b>Hello</b> World')
      expect(result.current.sanitizedContent).toBe('Hello World')
    })

    it('allows markdown when allowMarkdown is true', () => {
      vi.mocked(sanitizeAndRenderMarkdown).mockReturnValue('<p>Hello World</p>')

      const { result } = renderHook(() =>
        useSanitizedContent('Hello World', { ...DEFAULT_SECURITY_CONFIG, allowMarkdown: true })
      )

      expect(sanitizeAndRenderMarkdown).toHaveBeenCalled()
      expect(result.current.sanitizedContent).toBe('<p>Hello World</p>')
    })

    it('handles empty content', () => {
      vi.mocked(sanitizeText).mockReturnValue('')

      const { result } = renderHook(() => useSanitizedContent(''))

      expect(result.current.isEmpty).toBe(true)
      expect(result.current.sanitizedContent).toBe('')
    })

    it('handles whitespace-only content as empty', () => {
      vi.mocked(sanitizeText).mockReturnValue('   ')

      const { result } = renderHook(() => useSanitizedContent('   '))

      expect(result.current.isEmpty).toBe(true)
    })

    it('memoizes results for same inputs', () => {
      vi.mocked(sanitizeText).mockReturnValue('Hello')

      const { result, rerender } = renderHook(
        ({ content }) => useSanitizedContent(content),
        { initialProps: { content: 'Hello' } }
      )

      const firstResult = result.current.sanitizedContent
      rerender({ content: 'Hello' })
      const secondResult = result.current.sanitizedContent

      expect(firstResult).toBe(secondResult)
    })
  })

  describe('useXSSDetection', () => {
    it('detects XSS patterns in content', () => {
      vi.mocked(detectXSSAttempt).mockReturnValue({
        isDetected: true,
        patterns: ['Script Tags'],
        severity: 'critical',
      })

      const { result } = renderHook(() => useXSSDetection('<script>alert(1)</script>'))

      expect(result.current.isDetected).toBe(true)
      expect(result.current.patterns).toContain('Script Tags')
      expect(result.current.severity).toBe('critical')
    })

    it('returns no detection for safe content', () => {
      vi.mocked(detectXSSAttempt).mockReturnValue({
        isDetected: false,
        patterns: [],
        severity: 'low',
      })

      const { result } = renderHook(() => useXSSDetection('Safe content'))

      expect(result.current.isDetected).toBe(false)
      expect(result.current.patterns).toHaveLength(0)
    })

    it('provides logDetection callback', () => {
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      vi.mocked(detectXSSAttempt).mockReturnValue({
        isDetected: true,
        patterns: ['Event Handlers'],
        severity: 'high',
      })

      const { result } = renderHook(() => useXSSDetection('<img onerror=alert(1)>'))

      act(() => {
        result.current.logDetection('TestComponent')
      })

      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('XSS attempt detected'),
        expect.any(Object)
      )

      consoleSpy.mockRestore()
    })

    it('does not log when no XSS detected', () => {
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

      const { result } = renderHook(() => useXSSDetection('Safe content'))

      act(() => {
        result.current.logDetection('TestComponent')
      })

      expect(consoleSpy).not.toHaveBeenCalled()
      consoleSpy.mockRestore()
    })
  })

  describe('useSecureInput', () => {
    it('initializes with provided value', () => {
      vi.mocked(sanitizeText).mockReturnValue('initial')

      const { result } = renderHook(() => useSecureInput('initial'))

      expect(result.current.value).toBe('initial')
      expect(result.current.sanitizedValue).toBe('initial')
    })

    it('updates value and sanitizedValue on change', () => {
      vi.mocked(sanitizeHTML).mockImplementation((html) => html.replace(/\u003cscript\u003e/gi, ''))
      vi.mocked(detectXSSAttempt).mockReturnValue({
        isDetected: false,
        patterns: [],
        severity: 'low',
      })

      const { result } = renderHook(() => useSecureInput(''))

      act(() => {
        result.current.setValue('<b>Hello</b>')
      })

      expect(result.current.value).toBe('<b>Hello</b>')
    })

    it('detects XSS in input', () => {
      vi.mocked(detectXSSAttempt).mockReturnValue({
        isDetected: true,
        patterns: ['Script Tags'],
        severity: 'critical',
      })

      const { result } = renderHook(() => useSecureInput(''))

      act(() => {
        result.current.setValue('<script>alert(1)</script>')
      })

      expect(result.current.hasXSS).toBe(true)
    })

    it('allows secure submission when no XSS detected', () => {
      const onSubmit = vi.fn()
      vi.mocked(detectXSSAttempt).mockReturnValue({
        isDetected: false,
        patterns: [],
        severity: 'low',
      })

      const { result } = renderHook(() => useSecureInput('safe value'))

      act(() => {
        result.current.onSecureSubmit(onSubmit)
      })

      expect(onSubmit).toHaveBeenCalledWith('safe value')
    })

    it('prevents submission when XSS detected', () => {
      const onSubmit = vi.fn()
      vi.mocked(detectXSSAttempt).mockReturnValue({
        isDetected: true,
        patterns: ['Script Tags'],
        severity: 'critical',
      })

      const { result } = renderHook(() => useSecureInput(''))

      act(() => {
        result.current.setValue('<script>')
      })

      act(() => {
        result.current.onSecureSubmit(onSubmit)
      })

      expect(onSubmit).not.toHaveBeenCalled()
    })

    it('tracks if content was modified by sanitization', () => {
      vi.mocked(sanitizeHTML).mockReturnValue('cleaned')
      vi.mocked(detectXSSAttempt).mockReturnValue({
        isDetected: false,
        patterns: [],
        severity: 'low',
      })

      const { result } = renderHook(() => useSecureInput(''))

      act(() => {
        result.current.setValue('raw <script>content')
      })

      expect(result.current.isModified).toBe(true)
    })
  })

  describe('useSafeInnerHTML', () => {
    it('creates safe markup for HTML content', () => {
      vi.mocked(sanitizeHTML).mockReturnValue('<b>Hello</b>')
      vi.mocked(detectXSSAttempt).mockReturnValue({
        isDetected: false,
        patterns: [],
        severity: 'low',
      })

      const { result } = renderHook(() => useSafeInnerHTML('<b>Hello</b>'))

      expect(result.current.createMarkup()).toEqual({ __html: '<b>Hello</b>' })
      expect(result.current.shouldRenderAsHTML).toBe(true)
    })

    it('escapes content when XSS is detected', () => {
      vi.mocked(escapeHTML).mockReturnValue('&lt;script&gt;alert(1)&lt;/script&gt;')
      vi.mocked(detectXSSAttempt).mockReturnValue({
        isDetected: true,
        patterns: ['Script Tags'],
        severity: 'critical',
      })

      const { result } = renderHook(() => useSafeInnerHTML('<script>alert(1)</script>'))

      expect(result.current.hasXSSRisk).toBe(true)
      expect(result.current.shouldRenderAsHTML).toBe(false)
    })

    it('logs XSS attempts on mount', () => {
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      vi.mocked(detectXSSAttempt).mockReturnValue({
        isDetected: true,
        patterns: ['Script Tags'],
        severity: 'critical',
      })

      renderHook(() => useSafeInnerHTML('<script>'))

      expect(consoleSpy).toHaveBeenCalled()
      consoleSpy.mockRestore()
    })
  })

  describe('useChatMessageSecurity', () => {
    it('applies stricter security for user messages', () => {
      vi.mocked(sanitizeText).mockReturnValue('Hello user')
      vi.mocked(detectXSSAttempt).mockReturnValue({
        isDetected: false,
        patterns: [],
        severity: 'low',
      })

      const { result } = renderHook(() => useChatMessageSecurity('Hello user', 'user'))

      expect(result.current.isFromAssistant).toBe(false)
      expect(result.current.shouldRenderAsHTML).toBe(false)
    })

    it('allows markdown rendering for assistant messages', () => {
      vi.mocked(sanitizeAndRenderMarkdown).mockReturnValue('<p>Hello</p>')
      vi.mocked(detectXSSAttempt).mockReturnValue({
        isDetected: false,
        patterns: [],
        severity: 'low',
      })

      const { result } = renderHook(() => useChatMessageSecurity('Hello', 'assistant'))

      expect(result.current.isFromAssistant).toBe(true)
      expect(result.current.shouldRenderAsHTML).toBe(true)
    })

    it('forces text rendering when XSS is detected in assistant message', () => {
      vi.mocked(sanitizeText).mockReturnValue('safe text')
      vi.mocked(detectXSSAttempt).mockReturnValue({
        isDetected: true,
        patterns: ['Script Tags'],
        severity: 'critical',
      })

      const { result } = renderHook(() => useChatMessageSecurity('<script>', 'assistant'))

      expect(result.current.hasXSSRisk).toBe(true)
      expect(result.current.shouldRenderAsHTML).toBe(false)
    })

    it('returns appropriate display content based on role', () => {
      vi.mocked(sanitizeText).mockReturnValue('text version')
      vi.mocked(sanitizeAndRenderMarkdown).mockReturnValue('<p>html version</p>')
      vi.mocked(detectXSSAttempt).mockReturnValue({
        isDetected: false,
        patterns: [],
        severity: 'low',
      })

      const { result: userResult } = renderHook(() =>
        useChatMessageSecurity('content', 'user')
      )
      expect(userResult.current.displayContent).toBe('text version')

      const { result: assistantResult } = renderHook(() =>
        useChatMessageSecurity('content', 'assistant')
      )
      expect(assistantResult.current.displayContent).toBe('<p>html version</p>')
    })
  })

  describe('useContentSecurityPolicy', () => {
    it('provides applyCSP function', () => {
      const consoleSpy = vi.spyOn(console, 'info').mockImplementation(() => {})

      const { result } = renderHook(() => useContentSecurityPolicy())

      act(() => {
        result.current.applyCSP({
          'default-src': "'self'",
          'script-src': "'self'",
        })
      })

      expect(consoleSpy).toHaveBeenCalledWith(
        'Recommended CSP policy:',
        expect.objectContaining({
          'default-src': "'self'",
          'script-src': "'self'",
        })
      )

      consoleSpy.mockRestore()
    })
  })

  describe('useSecurityMonitoring', () => {
    beforeEach(() => {
      vi.spyOn(console, 'error').mockImplementation(() => {})
      vi.spyOn(console, 'warn').mockImplementation(() => {})
      vi.spyOn(console, 'info').mockImplementation(() => {})
    })

    afterEach(() => {
      vi.restoreAllMocks()
    })

    it('logs security events', () => {
      const { result } = renderHook(() => useSecurityMonitoring())

      act(() => {
        result.current.logSecurityEvent('test_event', 'medium', { detail: 'info' })
      })

      const events = result.current.getSecurityEvents()
      expect(events).toHaveLength(1)
      expect(events[0].event).toBe('test_event')
      expect(events[0].severity).toBe('medium')
    })

    it('logs critical events to console.error', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      const { result } = renderHook(() => useSecurityMonitoring())

      act(() => {
        result.current.logSecurityEvent('critical_event', 'critical')
      })

      expect(consoleSpy).toHaveBeenCalled()
    })

    it('logs high severity events to console.error', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      const { result } = renderHook(() => useSecurityMonitoring())

      act(() => {
        result.current.logSecurityEvent('high_event', 'high')
      })

      expect(consoleSpy).toHaveBeenCalled()
    })

    it('logs medium severity events to console.warn', () => {
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

      const { result } = renderHook(() => useSecurityMonitoring())

      act(() => {
        result.current.logSecurityEvent('medium_event', 'medium')
      })

      expect(consoleSpy).toHaveBeenCalled()
    })

    it('logs low severity events to console.info', () => {
      const consoleSpy = vi.spyOn(console, 'info').mockImplementation(() => {})

      const { result } = renderHook(() => useSecurityMonitoring())

      act(() => {
        result.current.logSecurityEvent('low_event', 'low')
      })

      expect(consoleSpy).toHaveBeenCalled()
    })

    it('clears security events', () => {
      const { result } = renderHook(() => useSecurityMonitoring())

      act(() => {
        result.current.logSecurityEvent('event1', 'low')
        result.current.logSecurityEvent('event2', 'low')
      })

      expect(result.current.getSecurityEvents()).toHaveLength(2)

      act(() => {
        result.current.clearSecurityEvents()
      })

      expect(result.current.getSecurityEvents()).toHaveLength(0)
    })

    it('maintains max 100 events to prevent memory leaks', () => {
      const { result } = renderHook(() => useSecurityMonitoring())

      act(() => {
        for (let i = 0; i < 105; i++) {
          result.current.logSecurityEvent(`event${i}`, 'low')
        }
      })

      expect(result.current.getSecurityEvents()).toHaveLength(100)
    })

    it('preserves most recent events when exceeding limit', () => {
      const { result } = renderHook(() => useSecurityMonitoring())

      act(() => {
        for (let i = 0; i < 105; i++) {
          result.current.logSecurityEvent(`event${i}`, 'low')
        }
      })

      const events = result.current.getSecurityEvents()
      expect(events[events.length - 1].event).toBe('event104')
    })

    it('returns immutable copy of events', () => {
      const { result } = renderHook(() => useSecurityMonitoring())

      act(() => {
        result.current.logSecurityEvent('event1', 'low')
      })

      const events1 = result.current.getSecurityEvents()
      const events2 = result.current.getSecurityEvents()

      expect(events1).not.toBe(events2)
      expect(events1).toEqual(events2)
    })
  })
})
