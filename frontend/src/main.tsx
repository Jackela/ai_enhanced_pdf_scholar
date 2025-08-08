import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import App from './App.tsx'
import { ThemeProvider } from './contexts/ThemeContext'
import { WebSocketProvider } from './contexts/WebSocketContext'
import { initializePreloading, addResourceHints } from './utils/preload'
import './index.css'

// Configure React Query
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 5 * 60 * 1000, // 5 minutes
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 1,
    },
  },
})

// Initialize performance optimizations
addResourceHints()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <WebSocketProvider>
          <App />
          <ReactQueryDevtools initialIsOpen={false} />
        </WebSocketProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>
)

// Initialize preloading after app mount
setTimeout(initializePreloading, 100)
