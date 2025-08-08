import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { useMutation } from '@tanstack/react-query'
import { Upload, X, FileText, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'
import { api } from '../lib/api.ts'
import { Button } from './ui/Button'
import { Input } from './ui/Input'
import { useToast } from '../hooks/useToast'
import { formatFileSize } from '../lib/utils.ts'

interface DocumentUploadProps {
  onClose: () => void
  onSuccess: () => void
}

interface UploadFile extends File {
  id: string
  customTitle?: string
  status: 'pending' | 'uploading' | 'success' | 'error'
  error?: string
  progress?: number
}

interface UploadOptions {
  check_duplicates: boolean
  auto_build_index: boolean
  title?: string
  custom_title?: string
}

function DocumentUpload({ onClose, onSuccess }: DocumentUploadProps) {
  const [files, setFiles] = useState<UploadFile[]>([])
  const [checkDuplicates, setCheckDuplicates] = useState(true)
  const [autoBuildIndex, setAutoBuildIndex] = useState(true)
  const { toast } = useToast()

  const uploadMutation = useMutation({
    mutationFn: async ({ file, options }: { file: UploadFile; options: UploadOptions }) => {
      // Update file status to uploading
      setFiles(prev =>
        prev.map(f => (f.id === file.id ? { ...f, status: 'uploading' as const } : f))
      )

      const result = await api.uploadDocument(file, options)

      // Update file status to success
      setFiles(prev => prev.map(f => (f.id === file.id ? { ...f, status: 'success' as const } : f)))

      return result
    },
    onError: (error, variables) => {
      const { file } = variables
      setFiles(prev =>
        prev.map(f =>
          f.id === file.id
            ? {
                ...f,
                status: 'error' as const,
                error: error instanceof Error ? error.message : 'Upload failed',
              }
            : f
        )
      )

      toast({
        title: 'Upload failed',
        description: `Failed to upload ${file.name}`,
        variant: 'destructive',
      })
    },
  })

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const newFiles: UploadFile[] = acceptedFiles.map(file => ({
      ...file,
      id: Math.random().toString(36).substr(2, 9),
      status: 'pending' as const,
    }))

    setFiles(prev => [...prev, ...newFiles])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
    },
    multiple: true,
  })

  const removeFile = (fileId: string) => {
    setFiles(prev => prev.filter(f => f.id !== fileId))
  }

  const updateFileTitle = (fileId: string, title: string) => {
    setFiles(prev => prev.map(f => (f.id === fileId ? { ...f, customTitle: title } : f)))
  }

  const handleUpload = async () => {
    const pendingFiles = files.filter(f => f.status === 'pending')

    if (pendingFiles.length === 0) {
      toast({
        title: 'No files to upload',
        description: 'Please add some PDF files first.',
      })
      return
    }

    let successCount = 0

    for (const file of pendingFiles) {
      try {
        await uploadMutation.mutateAsync({
          file,
          options: {
            title: file.customTitle || undefined,
            check_duplicates: checkDuplicates,
            auto_build_index: autoBuildIndex,
          },
        })
        successCount++
      } catch (error) {
        // Error is already handled in onError
      }
    }

    if (successCount > 0) {
      toast({
        title: 'Upload completed',
        description: `Successfully uploaded ${successCount} document${successCount > 1 ? 's' : ''}.`,
      })

      if (successCount === pendingFiles.length) {
        onSuccess()
      }
    }
  }

  const allCompleted =
    files.length > 0 && files.every(f => f.status === 'success' || f.status === 'error')
  const hasSuccessful = files.some(f => f.status === 'success')

  return (
    <div className='fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4'>
      <div className='bg-background rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden'>
        {/* Header */}
        <div className='flex items-center justify-between p-6 border-b'>
          <h2 className='text-xl font-semibold'>Upload Documents</h2>
          <Button variant='ghost' size='sm' onClick={onClose}>
            <X className='h-4 w-4' />
          </Button>
        </div>

        {/* Content */}
        <div className='p-6 space-y-6 max-h-[60vh] overflow-auto'>
          {/* Drop zone */}
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
              isDragActive
                ? 'border-primary bg-primary/5'
                : 'border-border hover:border-primary hover:bg-primary/5'
            }`}
          >
            <input {...getInputProps()} />
            <Upload className='h-12 w-12 text-muted-foreground mx-auto mb-4' />
            <div className='space-y-2'>
              <p className='text-lg font-medium'>
                {isDragActive ? 'Drop PDF files here' : 'Drag & drop PDF files here'}
              </p>
              <p className='text-sm text-muted-foreground'>or click to browse files</p>
              <p className='text-xs text-muted-foreground'>Supports PDF files up to 50MB each</p>
            </div>
          </div>

          {/* Options */}
          <div className='space-y-4'>
            <div className='flex items-center space-x-2'>
              <input
                type='checkbox'
                id='check-duplicates'
                checked={checkDuplicates}
                onChange={e => setCheckDuplicates(e.target.checked)}
                className='rounded border-border'
              />
              <label htmlFor='check-duplicates' className='text-sm font-medium'>
                Check for duplicates
              </label>
            </div>

            <div className='flex items-center space-x-2'>
              <input
                type='checkbox'
                id='auto-build-index'
                checked={autoBuildIndex}
                onChange={e => setAutoBuildIndex(e.target.checked)}
                className='rounded border-border'
              />
              <label htmlFor='auto-build-index' className='text-sm font-medium'>
                Automatically build search index
              </label>
            </div>
          </div>

          {/* File list */}
          {files.length > 0 && (
            <div className='space-y-3'>
              <h3 className='font-medium'>Files to upload ({files.length})</h3>
              <div className='space-y-2 max-h-60 overflow-auto'>
                {files.map(file => (
                  <div key={file.id} className='flex items-center gap-3 p-3 border rounded-lg'>
                    <div className='flex-shrink-0'>
                      {file.status === 'pending' && (
                        <FileText className='h-5 w-5 text-muted-foreground' />
                      )}
                      {file.status === 'uploading' && (
                        <Loader2 className='h-5 w-5 text-primary animate-spin' />
                      )}
                      {file.status === 'success' && (
                        <CheckCircle className='h-5 w-5 text-green-600' />
                      )}
                      {file.status === 'error' && <AlertCircle className='h-5 w-5 text-red-600' />}
                    </div>

                    <div className='flex-1 min-w-0'>
                      <div className='flex items-center gap-2 mb-1'>
                        <span className='font-medium truncate'>{file.name}</span>
                        <span className='text-xs text-muted-foreground'>
                          {formatFileSize(file.size)}
                        </span>
                      </div>

                      {file.status === 'pending' && (
                        <Input
                          placeholder='Custom title (optional)'
                          value={file.customTitle || ''}
                          onChange={e => updateFileTitle(file.id, e.target.value)}
                          className='text-sm h-8'
                        />
                      )}

                      {file.status === 'error' && file.error && (
                        <p className='text-xs text-red-600'>{file.error}</p>
                      )}

                      {file.status === 'success' && (
                        <p className='text-xs text-green-600'>Successfully uploaded</p>
                      )}
                    </div>

                    {file.status === 'pending' && (
                      <Button variant='ghost' size='sm' onClick={() => removeFile(file.id)}>
                        <X className='h-4 w-4' />
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className='flex items-center justify-between p-6 border-t bg-muted/20'>
          <div className='text-sm text-muted-foreground'>
            {files.length > 0 && (
              <span>
                {files.filter(f => f.status === 'success').length} successful,{' '}
                {files.filter(f => f.status === 'error').length} failed,{' '}
                {files.filter(f => f.status === 'pending').length} pending
              </span>
            )}
          </div>

          <div className='flex gap-2'>
            <Button variant='outline' onClick={onClose}>
              {allCompleted && hasSuccessful ? 'Done' : 'Cancel'}
            </Button>

            {!allCompleted && (
              <Button
                onClick={handleUpload}
                disabled={
                  files.filter(f => f.status === 'pending').length === 0 || uploadMutation.isPending
                }
              >
                {uploadMutation.isPending ? (
                  <>
                    <Loader2 className='h-4 w-4 mr-2 animate-spin' />
                    Uploading...
                  </>
                ) : (
                  'Upload Files'
                )}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// Default export for lazy loading
export default DocumentUpload

// Named export for backward compatibility
export { DocumentUpload }
