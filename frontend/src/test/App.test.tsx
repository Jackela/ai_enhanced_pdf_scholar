import { describe, it, expect, vi } from 'vitest'
import App from '../App'

// Mock the WebSocket context
vi.mock('../contexts/WebSocketContext', () => ({
  WebSocketProvider: ({ children }: { children: React.ReactNode }) => children,
  useWebSocket: () => ({
    isConnected: false,
    sendMessage: vi.fn(),
    lastMessage: null,
    connectionError: null,
    reconnect: vi.fn(),
  }),
}))

// Mock the toast hook
vi.mock('../hooks/useToast', () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}))

// Mock the Theme context
vi.mock('../contexts/ThemeContext', () => ({
  ThemeProvider: ({ children }: { children: React.ReactNode }) => children,
  useTheme: () => ({
    theme: 'light',
    setTheme: vi.fn(),
  }),
}))

// Test configuration removed - using simple smoke test approach

describe('App', () => {
  it('smoke test - imports correctly', () => {
    // Simple import test to ensure no syntax errors
    expect(App).toBeDefined()
    expect(typeof App).toBe('function')
  })
})
