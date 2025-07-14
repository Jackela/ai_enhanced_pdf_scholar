import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { Button } from '../ui/Button'
import { useToast } from '../../hooks/useToast'

export function DocumentViewer() {
  const { id } = useParams<{ id: string }>()
  const [document, setDocument] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const { toast } = useToast()

  useEffect(() => {
    if (id) {
      loadDocument(id)
    }
  }, [id])

  const loadDocument = async (documentId: string) => {
    try {
      setLoading(true)
      const response = await fetch(`/api/library/documents/${documentId}`)
      if (response.ok) {
        const doc = await response.json()
        setDocument(doc)
      } else {
        throw new Error('Document not found')
      }
    } catch (error) {
      console.error('Failed to load document:', error)
      toast({
        title: "加载失败",
        description: "无法加载文档",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">加载文档中...</p>
        </div>
      </div>
    )
  }

  if (!document) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <p className="text-gray-600 dark:text-gray-400 mb-4">文档未找到</p>
          <Button onClick={() => window.history.back()}>返回</Button>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          {document.title}
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          文档查看器 - {document.file_size} bytes
        </p>
      </div>
      
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
        <p className="text-center text-gray-500 dark:text-gray-400">
          PDF查看器将在未来版本中实现
        </p>
      </div>
    </div>
  )
}