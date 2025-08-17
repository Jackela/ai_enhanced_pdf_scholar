import React, { useState, useRef, useEffect } from 'react'
import { api } from '../../lib/api'
import { useToast } from '../../hooks/useToast'
import type { 
  DocumentCollection, 
  CrossDocumentQueryRequest, 
  MultiDocumentQueryResponse 
} from '../../types'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import CrossDocumentQueryResult from './CrossDocumentQueryResult'

interface CrossDocumentChatProps {
  collection: DocumentCollection
}

interface ChatMessage {
  id: string
  type: 'user' | 'assistant'
  content: string
  timestamp: Date
  queryResponse?: MultiDocumentQueryResponse
}

const CrossDocumentChat: React.FC<CrossDocumentChatProps> = ({ collection }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [currentQuery, setCurrentQuery] = useState('')
  const [isQuerying, setIsQuerying] = useState(false)
  const [maxResults, setMaxResults] = useState(10)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const { toast } = useToast()

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSubmitQuery = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!currentQuery.trim()) return

    const query = currentQuery.trim()
    setCurrentQuery('')
    setIsQuerying(true)

    // Add user message
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      type: 'user',
      content: query,
      timestamp: new Date(),
    }
    setMessages(prev => [...prev, userMessage])

    try {
      const request: CrossDocumentQueryRequest = {
        query,
        max_results: maxResults,
        user_id: 'frontend-user', // This could be dynamic based on authentication
      }

      const response = await api.queryCollection(collection.id, request)

      // Add assistant message with query response
      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        type: 'assistant',
        content: response.answer,
        timestamp: new Date(),
        queryResponse: response,
      }
      setMessages(prev => [...prev, assistantMessage])

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to process query'
      
      // Add error message
      const errorResponse: ChatMessage = {
        id: `error-${Date.now()}`,
        type: 'assistant',
        content: `Sorry, I encountered an error while processing your query: ${errorMessage}`,
        timestamp: new Date(),
      }
      setMessages(prev => [...prev, errorResponse])

      toast({
        title: 'Query Error',
        description: errorMessage,
        variant: 'destructive',
      })
    } finally {
      setIsQuerying(false)
    }
  }

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  const clearChat = () => {
    setMessages([])
  }

  return (
    <div className="flex flex-col h-[600px] bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
        <div>
          <h3 className="font-medium text-gray-900 dark:text-white">
            Cross-Document Query
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Ask questions across all {collection.document_count} documents
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <label className="text-sm text-gray-600 dark:text-gray-400">
            Max results:
          </label>
          <select
            value={maxResults}
            onChange={(e) => setMaxResults(Number(e.target.value))}
            className="border border-gray-300 dark:border-gray-600 rounded px-2 py-1 text-sm dark:bg-gray-700 dark:text-white"
          >
            <option value={5}>5</option>
            <option value={10}>10</option>
            <option value={20}>20</option>
            <option value={50}>50</option>
          </select>
          {messages.length > 0 && (
            <Button variant="outline" size="sm" onClick={clearChat}>
              Clear
            </Button>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-gray-500 dark:text-gray-400 mb-4">
              Start a conversation with your document collection
            </div>
            <div className="text-sm text-gray-400 dark:text-gray-500">
              Example queries:
              <ul className="mt-2 space-y-1">
                <li>• "What are the main themes across these documents?"</li>
                <li>• "Compare the methodologies mentioned in different papers"</li>
                <li>• "Find contradictions between the documents"</li>
              </ul>
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg p-3 ${
                    message.type === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white'
                  }`}
                >
                  <div className="text-sm mb-1">{message.content}</div>
                  <div className={`text-xs opacity-70 ${
                    message.type === 'user' ? 'text-blue-100' : 'text-gray-500 dark:text-gray-400'
                  }`}>
                    {formatTime(message.timestamp)}
                  </div>
                </div>
              </div>
            ))}

            {/* Show detailed query result for the last assistant message */}
            {messages.length > 0 && 
             messages[messages.length - 1].type === 'assistant' && 
             messages[messages.length - 1].queryResponse && (
              <div className="mt-4">
                <CrossDocumentQueryResult 
                  queryResponse={messages[messages.length - 1].queryResponse!}
                />
              </div>
            )}
          </>
        )}

        {/* Loading indicator */}
        {isQuerying && (
          <div className="flex justify-start">
            <div className="bg-gray-100 dark:bg-gray-700 rounded-lg p-3">
              <div className="flex items-center space-x-2">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-600"></div>
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  Analyzing documents...
                </span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-gray-200 dark:border-gray-700">
        <form onSubmit={handleSubmitQuery} className="flex space-x-2">
          <Input
            value={currentQuery}
            onChange={(e) => setCurrentQuery(e.target.value)}
            placeholder="Ask a question about your documents..."
            disabled={isQuerying}
            maxLength={1000}
            className="flex-1"
          />
          <Button
            type="submit"
            disabled={isQuerying || !currentQuery.trim()}
          >
            {isQuerying ? 'Querying...' : 'Send'}
          </Button>
        </form>
      </div>
    </div>
  )
}

export default CrossDocumentChat