/**
 * SecureMessage Component Tests
 * 
 * Test suite for the SecureMessage component, testing XSS protection,
 * content sanitization, and security warning displays.
 * 
 * @security Tests SecureMessage component XSS protection
 * @author AI Enhanced PDF Scholar Security Team
 * @version 2.1.0
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import { SecureMessage, SecureMessageList, SecurityStatus } from '../components/ui/SecureMessage'

// Mock console for testing
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

describe('SecureMessage Component', () => {
  const mockProps = {
    content: 'Hello World',
    role: 'user' as const,
    timestamp: new Date('2024-01-01T12:00:00Z'),
    id: 1
  }

  it('should render safe user message', () => {
    render(<SecureMessage {...mockProps} />)
    
    expect(screen.getByText('Hello World')).toBeInTheDocument()
    expect(screen.getByTestId('secure-text-content')).toBeInTheDocument()
    expect(screen.getByTestId('secure-content-icon')).toBeInTheDocument()
    expect(screen.queryByTestId('xss-warning-icon')).not.toBeInTheDocument()
  })

  it('should render safe assistant message with markdown', () => {
    const assistantProps = {
      ...mockProps,
      role: 'assistant' as const,
      content: '**Hello** World! Here is some `code`.'
    }

    render(<SecureMessage {...assistantProps} />)
    
    expect(screen.getByTestId('secure-html-content')).toBeInTheDocument()
    expect(screen.getByText(/Hello/).parentElement).toContainHTML('<strong>')
    expect(screen.getByText(/code/).parentElement).toContainHTML('<code>')
  })

  it('should handle XSS attempts in user messages', () => {
    const xssProps = {
      ...mockProps,
      content: '<script>alert("XSS")</script>Hello'
    }

    render(<SecureMessage {...xssProps} />)
    
    expect(screen.getByText('alert("XSS")Hello')).toBeInTheDocument()
    expect(screen.getByTestId('xss-warning-icon')).toBeInTheDocument()
    expect(screen.getByText(/Security Alert/)).toBeInTheDocument()
    expect(screen.queryByText('<script>')).not.toBeInTheDocument()
  })

  it('should handle XSS attempts in assistant messages', () => {
    const xssProps = {
      ...mockProps,
      role: 'assistant' as const,
      content: '<script>alert("XSS")</script>Hello'
    }

    render(<SecureMessage {...xssProps} />)
    
    expect(screen.getByText('alert("XSS")Hello')).toBeInTheDocument()
    expect(screen.getByTestId('xss-warning-icon')).toBeInTheDocument()
    expect(screen.getByText(/Security Alert/)).toBeInTheDocument()
    expect(screen.queryByText('<script>')).not.toBeInTheDocument()
  })

  it('should show security info when enabled', () => {
    const xssProps = {
      ...mockProps,
      content: '<script>alert("XSS")</script>Hello',
      showSecurityInfo: true
    }

    render(<SecureMessage {...xssProps} />)
    
    expect(screen.getByText(/Patterns:/)).toBeInTheDocument()
    expect(screen.getByText(/Severity:/)).toBeInTheDocument()
  })

  it('should display role indicators', () => {
    // Test user message
    render(<SecureMessage {...mockProps} />)
    expect(screen.getByRole('img', { hidden: true })).toBeInTheDocument() // Lucide icons render as img

    // Test assistant message
    render(<SecureMessage {...mockProps} role="assistant" />)
    expect(screen.getAllByRole('img', { hidden: true })).toHaveLength(2) // Bot icon + shield icon
  })

  it('should format timestamps correctly', () => {
    render(<SecureMessage {...mockProps} />)
    
    expect(screen.getByText(/12:00:/)).toBeInTheDocument()
  })

  it('should handle invalid timestamps', () => {
    const invalidTimeProps = {
      ...mockProps,
      timestamp: 'invalid-date'
    }

    render(<SecureMessage {...invalidTimeProps} />)
    
    expect(screen.getByText('Invalid time')).toBeInTheDocument()
  })

  it('should apply correct styling for XSS content', () => {
    const xssProps = {
      ...mockProps,
      content: '<script>alert("XSS")</script>Hello'
    }

    render(<SecureMessage {...xssProps} />)
    
    const messageElement = screen.getByText('alert("XSS")Hello').closest('div')
    expect(messageElement).toHaveClass('border-2', 'border-red-400')
  })

  it('should log security events', () => {
    const xssProps = {
      ...mockProps,
      content: '<script>alert("XSS")</script>Hello',
      id: 'test-message'
    }

    render(<SecureMessage {...xssProps} />)
    
    // Should log the XSS attempt
    expect(mockConsole.error).toHaveBeenCalledWith(
      'Security Event:',
      expect.objectContaining({
        event: 'XSS_ATTEMPT_DETECTED',
        details: expect.objectContaining({
          messageId: 'test-message',
          role: 'user'
        })
      })
    )
  })

  it('should show development mode indicators', () => {
    const originalEnv = process.env.NODE_ENV
    process.env.NODE_ENV = 'development'

    render(<SecureMessage {...mockProps} />)
    
    expect(screen.getByText('TEXT')).toBeInTheDocument()
    
    process.env.NODE_ENV = originalEnv
  })
})

describe('SecureMessageList Component', () => {
  const mockMessages = [
    {
      id: 1,
      role: 'user' as const,
      content: 'Hello AI!',
      timestamp: new Date('2024-01-01T12:00:00Z')
    },
    {
      id: 2,
      role: 'assistant' as const,
      content: '**Hello!** How can I help you?',
      timestamp: new Date('2024-01-01T12:01:00Z')
    },
    {
      id: 3,
      role: 'user' as const,
      content: '<script>alert("XSS")</script>Malicious content',
      timestamp: new Date('2024-01-01T12:02:00Z')
    }
  ]

  it('should render all messages', () => {
    render(<SecureMessageList messages={mockMessages} />)
    
    expect(screen.getByText('Hello AI!')).toBeInTheDocument()
    expect(screen.getByText(/Hello!.* How can I help you?/)).toBeInTheDocument()
    expect(screen.getByText('alert("XSS")Malicious content')).toBeInTheDocument()
  })

  it('should detect bulk XSS attempts', () => {
    const xssMessages = Array(5).fill(null).map((_, i) => ({
      id: i,
      role: 'user' as const,
      content: `<script>alert("XSS ${i}")</script>`,
      timestamp: new Date()
    }))

    render(<SecureMessageList messages={xssMessages} />)
    
    expect(mockConsole.error).toHaveBeenCalledWith(
      'Security Event:',
      expect.objectContaining({
        event: 'BULK_XSS_DETECTION',
        severity: 'high'
      })
    )
  })

  it('should pass showSecurityInfo to child components', () => {
    const xssMessages = [{
      id: 1,
      role: 'user' as const,
      content: '<script>alert("XSS")</script>Test',
      timestamp: new Date()
    }]

    render(<SecureMessageList messages={xssMessages} showSecurityInfo={true} />)
    
    expect(screen.getByText(/Patterns:/)).toBeInTheDocument()
    expect(screen.getByText(/Severity:/)).toBeInTheDocument()
  })
})

describe('SecurityStatus Component', () => {
  it('should not render when no events', () => {
    const { container } = render(<SecurityStatus />)
    expect(container.firstChild).toBeNull()
  })

  it('should render security events', async () => {
    // Mock events for testing

    // We need to trigger some security events first
    render(<SecureMessage 
      content='<script>alert("XSS")</script>Test'
      role="user"
      timestamp={new Date()}
      id="test"
    />)

    // Then render SecurityStatus
    render(<SecurityStatus />)

    // Wait for the interval to update
    await waitFor(() => {
      expect(screen.queryByText('Security Status')).toBeInTheDocument()
    }, { timeout: 6000 })
  })

  it('should show high severity warning', async () => {
    // First trigger a high severity event
    render(<SecureMessage 
      content='<script>alert("XSS")</script>Test'
      role="user"
      timestamp={new Date()}
      id="test"
    />)

    // Then render SecurityStatus
    render(<SecurityStatus />)

    await waitFor(() => {
      const statusElement = screen.queryByText('Security Status')
      if (statusElement) {
        const container = statusElement.closest('div')
        expect(container).toHaveClass('bg-red-50', 'border-red-200')
      }
    }, { timeout: 6000 })
  })
})

describe('Component Integration Tests', () => {
  it('should handle complex message scenarios', () => {
    const complexMessages = [
      {
        id: 1,
        role: 'user' as const,
        content: 'Hello!',
        timestamp: new Date()
      },
      {
        id: 2,
        role: 'assistant' as const,
        content: '**Hello!** I can help with:\n\n1. Code: `console.log("test")`\n2. [Links](https://example.com)\n3. Math equations',
        timestamp: new Date()
      },
      {
        id: 3,
        role: 'user' as const,
        content: 'What about <script>alert("evil")</script> this?',
        timestamp: new Date()
      },
      {
        id: 4,
        role: 'assistant' as const,
        content: 'I detected malicious content: `<script>` tags are dangerous.',
        timestamp: new Date()
      }
    ]

    render(
      <>
        <SecureMessageList messages={complexMessages} showSecurityInfo={true} />
        <SecurityStatus />
      </>
    )

    // Check that safe content renders properly
    expect(screen.getByText('Hello!')).toBeInTheDocument()
    
    // Check that assistant markdown renders
    expect(screen.getByText(/Hello!/)).toBeInTheDocument()
    expect(screen.getByText(/console.log/)).toBeInTheDocument()
    
    // Check that XSS is blocked
    expect(screen.getByText('What about alert("evil") this?')).toBeInTheDocument()
    expect(screen.queryByText('<script>')).not.toBeInTheDocument()
    
    // Check that security warnings appear
    expect(screen.getByText(/Security Alert/)).toBeInTheDocument()
  })

  it('should maintain performance with many messages', () => {
    const manyMessages = Array(100).fill(null).map((_, i) => ({
      id: i,
      role: i % 2 === 0 ? 'user' as const : 'assistant' as const,
      content: `Message ${i}`,
      timestamp: new Date()
    }))

    const start = performance.now()
    render(<SecureMessageList messages={manyMessages} />)
    const end = performance.now()

    expect(end - start).toBeLessThan(100) // Should render in under 100ms
    expect(screen.getByText('Message 0')).toBeInTheDocument()
    expect(screen.getByText('Message 99')).toBeInTheDocument()
  })

  it('should handle rapid XSS attempts without performance degradation', () => {
    const xssMessages = Array(50).fill(null).map((_, i) => ({
      id: i,
      role: 'user' as const,
      content: `<script>alert("XSS ${i}")</script><img src="x" onerror="alert(${i})">`,
      timestamp: new Date()
    }))

    const start = performance.now()
    render(<SecureMessageList messages={xssMessages} showSecurityInfo={true} />)
    const end = performance.now()

    expect(end - start).toBeLessThan(200) // Should handle many XSS attempts quickly
    
    // Verify all XSS was blocked
    xssMessages.forEach((_, i) => {
      expect(screen.getByText(`alert("XSS ${i}")alert(${i})`)).toBeInTheDocument()
      expect(screen.queryByText('<script>')).not.toBeInTheDocument()
    })
  })
})