import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { useToast } from '../../hooks/useToast'
import { useWebSocket } from '../../contexts/WebSocketContext'
import { SecureMessageList, SecurityStatus } from '../ui/SecureMessage'
import { useSecureInput, useContentSecurityPolicy, useSecurityMonitoring } from '../../hooks/useSecurity'
import { CSP_POLICIES } from '../../utils/security'
import { Shield, AlertTriangle } from 'lucide-react'

interface ChatMessage {
  id: string | number
  role: 'user' | 'assistant'
  content: string
  timestamp: string | Date
  document_id?: string
}

function ChatView() {
  const { documentId } = useParams<{ documentId?: string }>()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [showSecurityPanel, setShowSecurityPanel] = useState(false)
  
  // Security hooks
  const { applyCSP } = useContentSecurityPolicy()
  const { logSecurityEvent } = useSecurityMonitoring()
  const { 
    value: inputValue, 
    hasXSS, 
    setValue: setInputValue,
    onSecureSubmit 
  } = useSecureInput('')
  
  const { toast } = useToast()
  const { sendMessage, isConnected } = useWebSocket()

  // Apply Content Security Policy on component mount
  useEffect(() => {
    applyCSP(CSP_POLICIES.STRICT)
    logSecurityEvent('CSP_APPLIED', 'low', { policy: 'STRICT' })
  }, [applyCSP, logSecurityEvent])

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return

    // Check for XSS in input
    if (hasXSS) {
      toast({
        title: 'Security Alert',
        description: 'Your message contains potentially unsafe content and cannot be sent.',
        variant: 'destructive',
      })
      logSecurityEvent('XSS_INPUT_BLOCKED', 'high', { 
        input: inputValue.substring(0, 100),
        documentId 
      })
      return
    }

    if (!isConnected) {
      toast({
        title: '连接错误',
        description: 'WebSocket连接未建立',
        variant: 'destructive',
      })
      return
    }

    onSecureSubmit(async (secureContent) => {
      const userMessage: ChatMessage = {
        id: Date.now(),
        role: 'user',
        content: secureContent,
        timestamp: new Date(),
      }

      setMessages(prev => [...prev, userMessage])
      setInputValue('')
      setIsLoading(true)

      try {
        // Send sanitized content through WebSocket
        sendMessage({
          type: 'rag_query',
          document_id: documentId ? parseInt(documentId) : null,
          query: secureContent,
        })
        
        logSecurityEvent('SECURE_MESSAGE_SENT', 'low', { 
          messageId: userMessage.id,
          documentId 
        })
      } catch (error) {
        console.error('Failed to send message:', error)
        toast({
          title: '发送失败',
          description: '无法发送消息',
          variant: 'destructive',
        })
        setIsLoading(false)
        
        logSecurityEvent('MESSAGE_SEND_FAILED', 'medium', { 
          error: error instanceof Error ? error.message : 'Unknown error',
          documentId 
        })
      }
    })
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  // Mock WebSocket response handling (replace with actual implementation)
  useEffect(() => {
    // This would be replaced with actual WebSocket message handling
    // For now, we'll simulate AI responses for testing
    
    const handleAIResponse = (response: any) => {
      if (response.type === 'rag_response') {
        const assistantMessage: ChatMessage = {
          id: Date.now() + 1,
          role: 'assistant',
          content: response.content || 'No response received.',
          timestamp: new Date(),
        }
        
        setMessages(prev => [...prev, assistantMessage])
        setIsLoading(false)
        
        logSecurityEvent('AI_RESPONSE_RECEIVED', 'low', { 
          messageId: assistantMessage.id,
          documentId,
          contentLength: response.content?.length || 0
        })
      }
    }
    
    // Register WebSocket handler (this would be actual implementation)
    // In a real implementation, handleAIResponse would be used like:
    // webSocketClient.on('message', handleAIResponse)
    void handleAIResponse // Suppress unused variable warning
  }, [logSecurityEvent, documentId])

  return (
    <div className='h-full flex flex-col'>
      {/* Header */}
      <div className='border-b border-gray-200 dark:border-gray-700 p-4'>
        <div className="flex items-center justify-between">
          <div>
            <h1 className='text-xl font-semibold text-gray-900 dark:text-white'>
              {documentId ? `文档对话 #${documentId}` : 'AI对话'}
            </h1>
            <p className='text-sm text-gray-600 dark:text-gray-400'>
              与AI进行智能对话 {!isConnected && '(连接中...)'}
            </p>
          </div>
          
          {/* Security Panel Toggle */}
          <div className="flex items-center gap-2">
            {hasXSS && (
              <div className="flex items-center gap-1 text-red-600 dark:text-red-400">
                <AlertTriangle size={16} />
                <span className="text-xs">Input Warning</span>
              </div>
            )}
            
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowSecurityPanel(!showSecurityPanel)}
              className="flex items-center gap-2"
            >
              <Shield size={16} />
              Security
            </Button>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className='flex-1 overflow-y-auto p-4'>
        <div className="flex gap-4">
          {/* Messages Column */}
          <div className={`${showSecurityPanel ? 'flex-1' : 'w-full'} space-y-4`}>
            {messages.length === 0 ? (
              <div className='text-center text-gray-500 dark:text-gray-400'>
                <div className="flex items-center justify-center mb-4">
                  <Shield className="w-12 h-12 opacity-20" />
                </div>
                <p>开始与AI进行安全对话</p>
                <p className='text-sm mt-2'>
                  {documentId ? '询问关于文档的问题' : '询问任何问题'} - 所有内容都会经过XSS过滤
                </p>
                {process.env.NODE_ENV === 'development' && (
                  <div className="mt-4 text-xs opacity-50 bg-gray-100 dark:bg-gray-800 rounded p-2">
                    开发模式: XSS保护已启用 | CSP: STRICT
                  </div>
                )}
              </div>
            ) : (
              <SecureMessageList 
                messages={messages} 
                showSecurityInfo={showSecurityPanel}
              />
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

          {/* Security Panel */}
          {showSecurityPanel && (
            <div className="w-80 border-l border-gray-200 dark:border-gray-700 pl-4">
              <div className="sticky top-0">
                <h3 className="font-medium mb-4 flex items-center gap-2">
                  <Shield size={16} />
                  Security Monitor
                </h3>
                <SecurityStatus />
                
                {/* Security Info */}
                <div className="mt-4 space-y-3">
                  <div className="p-3 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
                    <div className="flex items-center gap-2 mb-2">
                      <Shield size={14} className="text-green-600" />
                      <span className="text-sm font-medium">XSS Protection</span>
                    </div>
                    <ul className="text-xs space-y-1 text-green-700 dark:text-green-300">
                      <li>• Content sanitization with DOMPurify</li>
                      <li>• Real-time XSS pattern detection</li>
                      <li>• Safe HTML rendering for AI responses</li>
                      <li>• URL validation and protocol filtering</li>
                    </ul>
                  </div>
                  
                  <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                    <div className="flex items-center gap-2 mb-2">
                      <Shield size={14} className="text-blue-600" />
                      <span className="text-sm font-medium">CSP Policy</span>
                    </div>
                    <p className="text-xs text-blue-700 dark:text-blue-300">
                      Strict Content Security Policy applied to prevent script injection.
                    </p>
                  </div>
                  
                  {hasXSS && (
                    <div className="p-3 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
                      <div className="flex items-center gap-2 mb-2">
                        <AlertTriangle size={14} className="text-red-600" />
                        <span className="text-sm font-medium">Input Alert</span>
                      </div>
                      <p className="text-xs text-red-700 dark:text-red-300">
                        Your current input contains potentially unsafe content. It will be sanitized before sending.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Input */}
      <div className='border-t border-gray-200 dark:border-gray-700 p-4'>
        <div className='space-y-2'>
          {/* Security warning for input */}
          {hasXSS && (
            <div className="flex items-center gap-2 text-red-600 dark:text-red-400 text-sm bg-red-50 dark:bg-red-900/20 px-3 py-2 rounded">
              <AlertTriangle size={16} />
              <span>
                Warning: Input contains potentially unsafe content. It will be sanitized.
              </span>
            </div>
          )}
          
          <div className='flex gap-2'>
            <Input
              value={inputValue}
              onChange={e => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={documentId ? '询问关于文档的问题...' : '输入您的问题...'}
              className={`flex-1 ${hasXSS ? 'border-red-300 dark:border-red-700' : ''}`}
              disabled={isLoading || !isConnected}
              title={hasXSS ? 'Input contains potentially unsafe content' : 'Secure input - XSS protection enabled'}
            />
            <Button
              onClick={handleSendMessage}
              disabled={!inputValue.trim() || isLoading || !isConnected}
              className={hasXSS ? 'bg-orange-600 hover:bg-orange-700' : ''}
              title={hasXSS ? 'Send (content will be sanitized)' : 'Send secure message'}
            >
              {hasXSS ? '⚠ 发送' : '发送'}
            </Button>
          </div>
          
          {/* Security status footer */}
          <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
            <div className="flex items-center gap-2">
              <Shield size={12} />
              <span>XSS 保护已启用</span>
            </div>
            {process.env.NODE_ENV === 'development' && (
              <span className="opacity-50">
                Dev Mode | CSP: Strict | Content Sanitized
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// Default export for lazy loading
export default ChatView

// Named export for backward compatibility
export { ChatView }
