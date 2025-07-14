// React import removed
import { Search, Bell, Settings, Moon, Sun, Monitor } from 'lucide-react'
import { useTheme } from '../contexts/ThemeContext'
import { useWebSocket } from '../contexts/WebSocketContext'
import { Button } from './ui/Button'
import { Input } from './ui/Input'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from './ui/DropdownMenu'

export function Header() {
  const { theme, setTheme } = useTheme()
  const { isConnected, connectionError } = useWebSocket()

  const themeIcons = {
    light: Sun,
    dark: Moon,
    system: Monitor,
  }

  const CurrentThemeIcon = themeIcons[theme]

  return (
    <header className="h-16 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 sticky top-0 z-50">
      <div className="flex h-full items-center justify-between px-6">
        {/* Search */}
        <div className="flex items-center flex-1 max-w-md">
          <div className="relative w-full">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
            <Input
              placeholder="Search documents..."
              className="pl-10 bg-muted/50 border-none focus-visible:ring-1"
            />
          </div>
        </div>

        {/* Right side actions */}
        <div className="flex items-center gap-2">
          {/* Connection status */}
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="hidden sm:inline">
              {isConnected ? 'Connected' : connectionError || 'Disconnected'}
            </span>
          </div>

          {/* Notifications */}
          <Button variant="ghost" size="sm" className="relative">
            <Bell className="h-4 w-4" />
            <span className="absolute -top-1 -right-1 h-3 w-3 bg-red-500 rounded-full text-xs" />
          </Button>

          {/* Theme toggle */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm">
                <CurrentThemeIcon className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => setTheme('light')}>
                <Sun className="h-4 w-4 mr-2" />
                Light
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setTheme('dark')}>
                <Moon className="h-4 w-4 mr-2" />
                Dark
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setTheme('system')}>
                <Monitor className="h-4 w-4 mr-2" />
                System
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Settings */}
          <Button variant="ghost" size="sm">
            <Settings className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </header>
  )
}