import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react'
import type { WebSocketMessage, RAGProgressMessage, RAGResponseMessage, IndexProgressMessage, ErrorMessage, DocumentUpdateMessage } from '../types'

interface WebSocketContextType {
  isConnected: boolean
  sendMessage: (message: any) => void
  lastMessage: WebSocketMessage | null
  connectionError: string | null
  reconnect: () => void
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined)

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const ws = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<number>()
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 5

  const connect = useCallback(() => {
    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/ws`
      
      ws.current = new WebSocket(wsUrl)

      ws.current.onopen = () => {
        console.log('WebSocket connected')
        setIsConnected(true)
        setConnectionError(null)
        reconnectAttempts.current = 0
      }

      ws.current.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          setLastMessage(message)
          
          // Log different message types for debugging
          switch (message.type) {
            case 'rag_progress':
              console.log('RAG Progress:', (message as RAGProgressMessage).message)
              break
            case 'rag_response':
              console.log('RAG Response received for document:', (message as RAGResponseMessage).document_id)
              break
            case 'index_progress':
              console.log('Index Progress:', (message as IndexProgressMessage).status)
              break
            case 'error':
              console.error('WebSocket Error:', (message as ErrorMessage).error)
              break
            case 'document_update':
              console.log('Document Update:', (message as DocumentUpdateMessage).action)
              break
          }
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }

      ws.current.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason)
        setIsConnected(false)
        
        if (!event.wasClean && reconnectAttempts.current < maxReconnectAttempts) {
          const delay = Math.pow(2, reconnectAttempts.current) * 1000 // Exponential backoff
          console.log(`Attempting to reconnect in ${delay}ms...`)
          
          reconnectTimeoutRef.current = window.setTimeout(() => {
            reconnectAttempts.current++
            connect()
          }, delay)
        } else if (reconnectAttempts.current >= maxReconnectAttempts) {
          setConnectionError('Failed to connect to server after multiple attempts')
        }
      }

      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error)
        setConnectionError('WebSocket connection error')
      }
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error)
      setConnectionError('Failed to create WebSocket connection')
    }
  }, [])

  const sendMessage = useCallback((message: any) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message))
    } else {
      console.warn('WebSocket is not connected')
    }
  }, [])

  const reconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    
    if (ws.current) {
      ws.current.close()
    }
    
    reconnectAttempts.current = 0
    setConnectionError(null)
    connect()
  }, [connect])

  useEffect(() => {
    connect()

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (ws.current) {
        ws.current.close()
      }
    }
  }, [connect])

  const value = {
    isConnected,
    sendMessage,
    lastMessage,
    connectionError,
    reconnect,
  }

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  )
}

export function useWebSocket() {
  const context = useContext(WebSocketContext)
  if (context === undefined) {
    throw new Error('useWebSocket must be used within a WebSocketProvider')
  }
  return context
}