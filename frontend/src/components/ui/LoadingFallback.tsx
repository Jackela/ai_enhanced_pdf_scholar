import { Loader2 } from 'lucide-react'

interface LoadingFallbackProps {
  message?: string
  size?: 'sm' | 'md' | 'lg'
}

export function LoadingFallback({ 
  message = 'Loading...', 
  size = 'md' 
}: LoadingFallbackProps) {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-8 w-8', 
    lg: 'h-12 w-12'
  }

  const containerClasses = {
    sm: 'min-h-[200px]',
    md: 'min-h-[400px]',
    lg: 'min-h-[600px]'
  }

  return (
    <div className={`flex flex-col items-center justify-center ${containerClasses[size]} p-8`}>
      <Loader2 className={`${sizeClasses[size]} animate-spin text-primary mb-4`} />
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  )
}

// Export a default loading component for route fallbacks
export default function RouteLoadingFallback() {
  return <LoadingFallback message="Loading page..." size="md" />
}