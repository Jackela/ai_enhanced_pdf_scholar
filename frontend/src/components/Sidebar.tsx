// React import removed
import { NavLink, useLocation } from 'react-router-dom'
import { 
  Library, 
  MessageSquare, 
  Settings, 
  Upload, 
  TrendingUp,
  FileText,
  Search,
  Menu,
  X 
} from 'lucide-react'
import { Button } from './ui/Button'
import { cn } from '../lib/utils'

interface SidebarProps {
  isOpen: boolean
  onToggle: () => void
}

const navigation = [
  { name: 'Library', href: '/library', icon: Library },
  { name: 'Chat', href: '/chat', icon: MessageSquare },
  { name: 'Settings', href: '/settings', icon: Settings },
]

const quickActions = [
  { name: 'Upload Document', icon: Upload, action: 'upload' },
  { name: 'Search All', icon: Search, action: 'search' },
  { name: 'View Analytics', icon: TrendingUp, action: 'analytics' },
]

export function Sidebar({ isOpen, onToggle }: SidebarProps) {
  const location = useLocation()

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        {isOpen && (
          <div className="flex items-center space-x-2">
            <FileText className="h-6 w-6 text-primary" />
            <span className="font-semibold text-lg">PDF Scholar</span>
          </div>
        )}
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggle}
          className="h-8 w-8 p-0"
        >
          {isOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
        </Button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4">
        <div className="space-y-2">
          {navigation.map((item) => {
            const Icon = item.icon
            const isActive = location.pathname === item.href || 
                           (item.href === '/library' && location.pathname === '/')
            
            return (
              <NavLink
                key={item.name}
                to={item.href}
                className={cn(
                  'flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground',
                  isActive && 'bg-accent text-accent-foreground',
                  !isOpen && 'justify-center'
                )}
              >
                <Icon className="h-5 w-5 flex-shrink-0" />
                {isOpen && <span>{item.name}</span>}
              </NavLink>
            )
          })}
        </div>

        {/* Quick Actions */}
        {isOpen && (
          <div className="mt-8">
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
              Quick Actions
            </h3>
            <div className="space-y-1">
              {quickActions.map((action) => {
                const Icon = action.icon
                return (
                  <button
                    key={action.action}
                    className="flex items-center space-x-3 w-full px-3 py-2 text-left rounded-lg text-sm font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
                  >
                    <Icon className="h-4 w-4" />
                    <span>{action.name}</span>
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </nav>

      {/* Footer */}
      {isOpen && (
        <div className="p-4 border-t border-border">
          <div className="text-xs text-muted-foreground">
            <p>AI Enhanced PDF Scholar</p>
            <p>Version 2.0.0</p>
          </div>
        </div>
      )}
    </div>
  )
}