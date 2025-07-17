import React from 'react'
import { BrowserRouter } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Toaster } from './components/ui/Toaster'
import { useTheme } from './contexts/ThemeContext'

function App() {
  const { theme } = useTheme()

  // Apply theme class to document element
  React.useEffect(() => {
    const root = document.documentElement
    root.classList.remove('light', 'dark')

    if (theme === 'system') {
      const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'
      root.classList.add(systemTheme)
    } else {
      root.classList.add(theme)
    }
  }, [theme])

  return (
    <BrowserRouter>
      <div className='min-h-screen bg-background font-sans antialiased'>
        <Layout />
        <Toaster />
      </div>
    </BrowserRouter>
  )
}

export default App
