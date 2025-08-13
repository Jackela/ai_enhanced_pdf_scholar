import { useState, Suspense, lazy } from 'react'
import { Routes, Route } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { SystemStatus } from './SystemStatus'
import { LoadingFallback } from './ui/LoadingFallback'

// Route-based code splitting with React.lazy
const LibraryView = lazy(() => import('./views/LibraryView'))
const DocumentViewer = lazy(() => import('./views/DocumentViewer'))
const ChatView = lazy(() => import('./views/ChatView'))
const SettingsView = lazy(() => import('./views/SettingsView'))
const MonitoringDashboard = lazy(() => import('./views/MonitoringDashboard'))

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(true)

  return (
    <div className='flex h-screen bg-background'>
      {/* Sidebar */}
      <div
        className={`${sidebarOpen ? 'w-80' : 'w-16'} transition-all duration-300 ease-in-out border-r border-border bg-muted/10`}
      >
        <Sidebar isOpen={sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)} />
      </div>

      {/* Main content */}
      <div className='flex-1 flex flex-col min-w-0'>
        <Header />

        <main className='flex-1 overflow-hidden'>
          <Suspense fallback={<LoadingFallback />}>
            <Routes>
              <Route path='/' element={<LibraryView />} />
              <Route path='/library' element={<LibraryView />} />
              <Route path='/document/:id' element={<DocumentViewer />} />
              <Route path='/chat' element={<ChatView />} />
              <Route path='/chat/:documentId' element={<ChatView />} />
              <Route path='/monitoring' element={<MonitoringDashboard />} />
              <Route path='/settings' element={<SettingsView />} />
            </Routes>
          </Suspense>
        </main>

        {/* System status bar */}
        <SystemStatus />
      </div>
    </div>
  )
}
