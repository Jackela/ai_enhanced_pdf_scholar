import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { useToast } from '../../hooks/useToast'
import { useWebSocket } from '../../contexts/WebSocketContext'

interface ChatMessage {
  id: string | number
  role: 'user' | 'assistant'
  content: string
  timestamp: string | Date
  document_id?: string
}

export function ChatView() {
  const { documentId } = useParams<{ documentId?: string }>()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const { toast } = useToast()
  const { sendMessage, isConnected } = useWebSocket()

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return

    if (!isConnected) {
      toast({
        title: '连接错误',
        description: 'WebSocket连接未建立',
        variant: 'destructive',
      })
      return
    }

    const userMessage: ChatMessage = {
      id: Date.now(),
      role: 'user',
      content: inputValue,
      timestamp: new Date(),
    }

    setMessages(prev => [...prev, userMessage])
    setInputValue('')
    setIsLoading(true)

    try {
      // Send RAG query through WebSocket
      sendMessage({
        type: 'rag_query',
        document_id: documentId ? parseInt(documentId) : null,
        query: inputValue,
      })
    } catch (error) {
      console.error('Failed to send message:', error)
      toast({
        title: '发送失败',
        description: '无法发送消息',
        variant: 'destructive',
      })
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  return (
    <div className='h-full flex flex-col'>
      {/* Header */}
      <div className='border-b border-gray-200 dark:border-gray-700 p-4'>
        <h1 className='text-xl font-semibold text-gray-900 dark:text-white'>
          {documentId ? `文档对话 #${documentId}` : 'AI对话'}
        </h1>
        <p className='text-sm text-gray-600 dark:text-gray-400'>
          与AI进行智能对话 {!isConnected && '(连接中...)'}
        </p>
      </div>

      {/* Messages */}
      <div className='flex-1 overflow-y-auto p-4 space-y-4'>
        {messages.length === 0 ? (
          <div className='text-center text-gray-500 dark:text-gray-400'>
            <p>开始与AI对话</p>
            <p className='text-sm mt-2'>{documentId ? '询问关于文档的问题' : '询问任何问题'}</p>
          </div>
        ) : (
          messages.map(message => (
            <div
              key={message.id}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-sm lg:max-w-md px-4 py-2 rounded-lg ${
                  message.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white'
                }`}
              >
                <p className='whitespace-pre-wrap'>{message.content}</p>
                <p className='text-xs opacity-70 mt-1'>
                  {message.timestamp instanceof Date
                    ? message.timestamp.toLocaleTimeString()
                    : new Date(message.timestamp).toLocaleTimeString()}
                </p>
              </div>
            </div>
          ))
        )}

        {isLoading && (
          <div className='flex justify-start'>
            <div className='bg-gray-200 dark:bg-gray-700 rounded-lg px-4 py-2'>
              <div className='flex items-center space-x-2'>
                <div className='w-2 h-2 bg-gray-500 rounded-full animate-pulse'></div>
                <div
                  className='w-2 h-2 bg-gray-500 rounded-full animate-pulse'
                  style={{ animationDelay: '0.2s' }}
                ></div>
                <div
                  className='w-2 h-2 bg-gray-500 rounded-full animate-pulse'
                  style={{ animationDelay: '0.4s' }}
                ></div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className='border-t border-gray-200 dark:border-gray-700 p-4'>
        <div className='flex gap-2'>
          <Input
            value={inputValue}
            onChange={e => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={documentId ? '询问关于文档的问题...' : '输入您的问题...'}
            className='flex-1'
            disabled={isLoading || !isConnected}
          />
          <Button
            onClick={handleSendMessage}
            disabled={!inputValue.trim() || isLoading || !isConnected}
          >
            发送
          </Button>
        </div>
      </div>
    </div>
  )
}
