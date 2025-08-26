/**
 * Preload utility for dynamically imported components and resources
 * Implements intelligent preloading strategies based on user behavior
 */

// Route preloading map
const routePreloaders = {
  library: () => import('../components/views/LibraryView'),
  collections: () => import('../components/views/CollectionsView'),
  document: () => import('../components/views/DocumentViewer'),
  chat: () => import('../components/views/ChatView'),
  settings: () => import('../components/views/SettingsView'),
  monitoring: () => import('../components/views/MonitoringDashboard'),
  upload: () => import('../components/DocumentUpload'),
} as const

type RouteKey = keyof typeof routePreloaders

// Track preloaded routes to avoid duplicate requests
const preloadedRoutes = new Set<RouteKey>()

/**
 * Preload a specific route component
 */
export function preloadRoute(route: RouteKey): Promise<any> {
  if (preloadedRoutes.has(route)) {
    return Promise.resolve()
  }

  preloadedRoutes.add(route)
  
  try {
    return routePreloaders[route]()
  } catch (error) {
    console.warn(`Failed to preload route: ${route}`, error)
    preloadedRoutes.delete(route) // Allow retry
    return Promise.reject(error)
  }
}

/**
 * Preload multiple routes with optional delay
 */
export function preloadRoutes(routes: RouteKey[], delayMs: number = 0): Promise<any[]> {
  if (delayMs > 0) {
    return new Promise(resolve => {
      setTimeout(() => {
        resolve(Promise.all(routes.map(route => preloadRoute(route))))
      }, delayMs)
    })
  }
  
  return Promise.all(routes.map(route => preloadRoute(route)))
}

/**
 * Preload critical routes for initial app load
 * Uses requestIdleCallback for non-blocking preloading
 */
export function preloadCriticalRoutes(): void {
  // Preload LibraryView as it's likely the first route users visit
  const criticalRoutes: RouteKey[] = ['library']
  
  if ('requestIdleCallback' in window) {
    requestIdleCallback(() => {
      preloadRoutes(criticalRoutes).catch(error => 
        console.warn('Failed to preload critical routes:', error)
      )
    }, { timeout: 2000 })
  } else {
    // Fallback for browsers without requestIdleCallback
    setTimeout(() => {
      preloadRoutes(criticalRoutes).catch(error => 
        console.warn('Failed to preload critical routes:', error)
      )
    }, 1000)
  }
}

/**
 * Preload route on hover/focus (for navigation links)
 */
export function createPreloadHandler(route: RouteKey) {
  let timeoutId: number | null = null
  
  const handleMouseEnter = () => {
    // Preload after 150ms delay to avoid unnecessary requests on quick hovers
    timeoutId = window.setTimeout(() => {
      preloadRoute(route).catch(error => 
        console.warn(`Failed to preload route on hover: ${route}`, error)
      )
    }, 150)
  }
  
  const handleMouseLeave = () => {
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
    }
  }
  
  return { onMouseEnter: handleMouseEnter, onMouseLeave: handleMouseLeave }
}

/**
 * Preload based on user intent prediction
 * Analyzes user behavior patterns to preload likely next routes
 */
export class SmartPreloader {
  private navigationHistory: string[] = []
  private interactionPatterns: Map<string, string[]> = new Map()
  
  /**
   * Track user navigation for pattern analysis
   */
  trackNavigation(from: string, to: string) {
    this.navigationHistory.push(to)
    
    // Keep only last 10 navigations
    if (this.navigationHistory.length > 10) {
      this.navigationHistory.shift()
    }
    
    // Update patterns
    if (!this.interactionPatterns.has(from)) {
      this.interactionPatterns.set(from, [])
    }
    this.interactionPatterns.get(from)!.push(to)
  }
  
  /**
   * Predict and preload likely next routes
   */
  predictAndPreload(currentRoute: string) {
    const patterns = this.interactionPatterns.get(currentRoute)
    if (!patterns || patterns.length === 0) return
    
    // Find most common next route
    const routeCounts = patterns.reduce((acc, route) => {
      acc[route] = (acc[route] || 0) + 1
      return acc
    }, {} as Record<string, number>)
    
    const mostLikelyNext = Object.entries(routeCounts)
      .sort(([,a], [,b]) => b - a)
      .slice(0, 2) // Top 2 most likely routes
      .map(([route]) => route)
    
    // Preload likely routes
    mostLikelyNext.forEach(route => {
      if (route in routePreloaders) {
        preloadRoute(route as RouteKey).catch(() => {})
      }
    })
  }
}

// Global smart preloader instance
export const smartPreloader = new SmartPreloader()

/**
 * Initialize preloading system
 */
export function initializePreloading(): void {
  // Preload critical routes
  preloadCriticalRoutes()
  
  // Set up intersection observer for preloading visible links
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const link = entry.target as HTMLElement
          const route = link.getAttribute('data-preload-route') as RouteKey
          if (route && route in routePreloaders) {
            preloadRoute(route).catch(() => {})
          }
        }
      })
    }, { rootMargin: '50px' })
    
    // Observe all links with preload attributes
    setTimeout(() => {
      document.querySelectorAll('[data-preload-route]').forEach(link => {
        observer.observe(link)
      })
    }, 1000)
  }
}

/**
 * Resource hints for critical assets
 */
export function addResourceHints(): void {
  const head = document.head
  
  // Preload critical fonts
  const fontPreload = document.createElement('link')
  fontPreload.rel = 'preload'
  fontPreload.href = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap'
  fontPreload.as = 'style'
  fontPreload.crossOrigin = 'anonymous'
  head.appendChild(fontPreload)
  
  // DNS prefetch for API endpoints
  const dnsPrefetch = document.createElement('link')
  dnsPrefetch.rel = 'dns-prefetch'
  dnsPrefetch.href = '//localhost:8000'
  head.appendChild(dnsPrefetch)
}