import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import { resolve } from 'path'
import type { Plugin } from 'vite'

// CSP Plugin for Vite
function cspPlugin(): Plugin {
  return {
    name: 'csp-plugin',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        // Development CSP headers
        const csp = [
          "default-src 'self'",
          "script-src 'self' 'unsafe-inline' 'unsafe-eval'", // Allow unsafe for HMR
          "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
          "font-src 'self' https://fonts.gstatic.com https:",
          "img-src 'self' data: https: http:",
          "connect-src 'self' ws: wss: http://localhost:* https://localhost:*",
          "frame-src 'self'",
          "object-src 'none'",
          "base-uri 'self'",
          "form-action 'self'"
        ].join('; ')
        
        res.setHeader('Content-Security-Policy', csp)
        res.setHeader('X-Content-Type-Options', 'nosniff')
        res.setHeader('X-Frame-Options', 'DENY')
        res.setHeader('X-XSS-Protection', '1; mode=block')
        res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin')
        next()
      })
    },
    generateBundle(options, bundle) {
      // Production CSP injection
      if (options.format === 'es') {
        const htmlFiles = Object.keys(bundle).filter(fileName => fileName.endsWith('.html'))
        
        htmlFiles.forEach(fileName => {
          const htmlChunk = bundle[fileName] as any
          if (htmlChunk.source) {
            // Inject CSP meta tag
            const csp = [
              "default-src 'self'",
              "script-src 'self'",
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
              "font-src 'self' https://fonts.gstatic.com",
              "img-src 'self' data: https:",
              "connect-src 'self' ws: wss:",
              "frame-src 'none'",
              "object-src 'none'",
              "base-uri 'self'",
              "form-action 'self'",
              "frame-ancestors 'none'",
              "upgrade-insecure-requests",
              "block-all-mixed-content"
            ].join('; ')
            
            const metaTag = `<meta http-equiv="Content-Security-Policy" content="${csp}">`
            htmlChunk.source = htmlChunk.source.replace('<head>', `<head>\n    ${metaTag}`)
          }
        })
      }
    }
  }
}

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const isProduction = mode === 'production'
  // Enhanced CI detection for different environments  
  const isCIBuild = env.CI === 'true' || process.env.CI === 'true' || !!process.env.CI || 
                     process.env.GITHUB_ACTIONS === 'true' || process.env.NODE_ENV === 'production'
  
  // Debug CI detection in GitHub Actions
  if (process.env.GITHUB_ACTIONS) {
    console.log('🔍 CI Detection Debug:', {
      'env.CI': env.CI,
      'process.env.CI': process.env.CI,
      'process.env.GITHUB_ACTIONS': process.env.GITHUB_ACTIONS,
      'process.env.NODE_ENV': process.env.NODE_ENV,
      'isCIBuild': isCIBuild,
      'mode': mode
    })
  }
  
  // Note: Project root is available via process.env.VITE_PROJECT_ROOT if needed

  return {
    plugins: [
      react({
        // Optimize React refresh for development
        fastRefresh: !isProduction,
        // Enable JSX runtime optimization
        jsxRuntime: 'automatic'
      }),
      cspPlugin(), // Add CSP plugin for security headers
      VitePWA({
        registerType: 'autoUpdate',
        disable: isCIBuild, // Disable PWA plugin in CI to avoid path resolution conflicts
        workbox: {
          globPatterns: ['**/*.{js,css,html,ico,png,svg}'],
          // Enhanced caching for production with compression
          runtimeCaching: isProduction ? [
            {
              urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
              handler: 'CacheFirst',
              options: {
                cacheName: 'google-fonts-cache',
                expiration: {
                  maxEntries: 10,
                  maxAgeSeconds: 60 * 60 * 24 * 365 // 1 year
                }
              }
            },
            {
              urlPattern: /\.(?:js|css)$/,
              handler: 'StaleWhileRevalidate',
              options: {
                cacheName: 'static-assets',
                cacheKeyWillBeUsed: async ({ request }) => {
                  // Add compression info to cache key
                  const url = new URL(request.url)
                  return `${url.pathname}${url.search}`
                }
              }
            }
          ] : []
        },
        manifest: {
          name: 'AI Enhanced PDF Scholar',
          short_name: 'PDF Scholar',
          description: 'Intelligent PDF document management and analysis',
          theme_color: '#0078d4',
          background_color: '#ffffff',
          display: 'standalone',
          icons: [
            {
              src: 'pwa-192x192.png',
              sizes: '192x192',
              type: 'image/png'
            },
            {
              src: 'pwa-512x512.png',
              sizes: '512x512',
              type: 'image/png'
            }
          ]
        }
      }),
    ],
    resolve: {
      alias: [
        // CRITICAL: Specific file mappings using __dirname for CI timing reliability
        { find: '@/lib/utils', replacement: resolve(__dirname, 'src/lib/utils.ts') },
        { find: '@/lib/api', replacement: resolve(__dirname, 'src/lib/api.ts') },
        
        // SECONDARY: Directory patterns using __dirname for CI timing reliability
        { find: /^@\/components\/(.*)/, replacement: resolve(__dirname, 'src/components/$1') },
        { find: /^@\/pages\/(.*)/, replacement: resolve(__dirname, 'src/pages/$1') },
        { find: /^@\/hooks\/(.*)/, replacement: resolve(__dirname, 'src/hooks/$1') },
        { find: /^@\/services\/(.*)/, replacement: resolve(__dirname, 'src/services/$1') },
        { find: /^@\/store\/(.*)/, replacement: resolve(__dirname, 'src/store/$1') },
        { find: /^@\/types\/(.*)/, replacement: resolve(__dirname, 'src/types/$1') },
        { find: /^@\/utils\/(.*)/, replacement: resolve(__dirname, 'src/utils/$1') },
        
        // BASE: Root @ mapping (must be last) using __dirname for consistency
        { find: '@', replacement: resolve(__dirname, 'src') }
      ],
      
      // Enhanced extension resolution prioritizing TypeScript
      extensions: ['.ts', '.tsx', '.js', '.jsx', '.json', '.mjs'],
      
      // Force resolution to prioritize exact file matches
      conditions: ['import', 'module', 'browser', 'default'],
      
      // Ensure consistent symlink handling across environments
      preserveSymlinks: false,
      
      // Enhanced alias resolution for CI environments
      mainFields: ['browser', 'module', 'main'],
      
      // Force case-sensitive resolution for consistency
      ...(isCIBuild && {
        caseSensitive: true
      })
    },
    server: {
      port: 3000,
      host: true, // Enable network access for development
      open: !isCIBuild, // Don't open browser in CI
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          secure: false
        },
        '/ws': {
          target: 'ws://localhost:8000',
          ws: true,
          changeOrigin: true
        }
      }
    },
    
    build: {
      outDir: 'dist',
      // Enable source maps in development, disable in CI for faster builds
      sourcemap: !isCIBuild && !isProduction ? 'inline' : false,
      // Optimize for CI builds
      minify: isProduction ? 'esbuild' : false,
      target: 'es2020',
      // Increase chunk size warning limit
      chunkSizeWarningLimit: 1000,
      // Enable build optimizations for production
      cssCodeSplit: isProduction,
      
      // Asset optimization
      assetsInlineLimit: 4096, // Inline assets smaller than 4KB
      
      rollupOptions: {
        // PWA-compatible path resolver with proper priority ordering
        plugins: [
          {
            name: 'ci-path-resolver',
            order: 'pre', // Critical: run before PWA plugin
            resolveId(id, _importer) {
              // Direct file mappings using __dirname for CI timing reliability
              if (id === '@/lib/utils') {
                return resolve(__dirname, 'src/lib/utils.ts')
              }
              if (id === '@/lib/api') {
                return resolve(__dirname, 'src/lib/api.ts')
              }
              return null
            }
          }
        ],
        
        output: {
          // Advanced chunk splitting for optimal caching and loading
          manualChunks: (id) => {
            // Core React libraries - critical for initial load
            if (id.includes('react-dom') || id.includes('react/jsx-runtime')) {
              return 'react-core'
            }
            if (id.includes('react-router-dom') || (id.includes('react') && !id.includes('react-dom'))) {
              return 'react-router'
            }
            
            // Animation library - heavy, separate chunk
            if (id.includes('framer-motion')) {
              return 'animation-vendor'
            }
            
            // PDF processing libraries - lazy load when needed
            if (id.includes('pdfjs-dist') || id.includes('react-pdf')) {
              return 'pdf-vendor'
            }
            
            // Icons - frequently used across app
            if (id.includes('lucide-react')) {
              return 'icons-vendor'
            }
            
            // UI components - split Radix UI separately
            if (id.includes('@radix-ui/')) {
              return 'radix-vendor'
            }
            
            // State management and data fetching
            if (id.includes('@tanstack/react-query')) {
              return 'query-vendor'
            }
            if (id.includes('zustand')) {
              return 'state-vendor'
            }
            
            // Network utilities
            if (id.includes('axios')) {
              return 'network-vendor'
            }
            
            // Utility libraries
            if (id.includes('clsx') || id.includes('tailwind-merge') || 
                id.includes('date-fns') || id.includes('class-variance-authority')) {
              return 'utils-vendor'
            }
            
            // Markdown and content processing
            if (id.includes('marked') || id.includes('dompurify') || 
                id.includes('react-markdown') || id.includes('remark-gfm') ||
                id.includes('react-syntax-highlighter')) {
              return 'content-vendor'
            }
            
            // Development tools - separate chunk
            if (id.includes('react-query-devtools')) {
              return 'dev-vendor'
            }
            
            // Toast and notification libraries
            if (id.includes('react-hot-toast') || id.includes('sonner')) {
              return 'notification-vendor'
            }
            
            // File handling
            if (id.includes('react-dropzone')) {
              return 'file-vendor'
            }
            
            // All other node_modules
            if (id.includes('node_modules')) {
              return 'vendor'
            }
          },
          
          // Optimize chunk file names for caching
          chunkFileNames: (chunkInfo) => {
            const facadeModuleId = chunkInfo.facadeModuleId
            if (facadeModuleId) {
              const name = facadeModuleId.split('/').pop()?.replace('.tsx', '').replace('.ts', '')
              return `chunks/${name}-[hash].js`
            }
            return 'chunks/[name]-[hash].js'
          },
          
          entryFileNames: 'assets/[name]-[hash].js',
          assetFileNames: 'assets/[name]-[hash].[ext]',
          
          // Enhanced code generation for better compression
          generatedCode: {
            constBindings: true,
            arrowFunctions: true,
            objectShorthand: true
          }
        },
        
        // Optimize external dependencies  
        external: isProduction ? [] : ['react', 'react-dom'],
        
        // Advanced tree shaking configuration
        treeshake: {
          moduleSideEffects: (id) => {
            // Allow side effects for CSS and specific modules
            if (id.includes('.css') || id.includes('.scss')) return true
            if (id.includes('react-hot-toast')) return true
            if (id.includes('framer-motion')) return true
            return false
          },
          // Use strict mode for better tree shaking
          preset: 'smallest',
          // Remove unused imports
          pureExternalModules: true
        }
      },
      
      // Build performance optimizations
      reportCompressedSize: !isCIBuild, // Skip compression reporting in CI for speed
      
      // Enhanced esbuild configuration for tree shaking
      esbuild: {
        // Remove console logs in production
        drop: isProduction ? ['console', 'debugger'] : [],
        // Optimize for faster builds in CI
        logOverride: isCIBuild ? { 'this-is-undefined-in-esm': 'silent' } : {},
        // Enhanced tree shaking
        treeShaking: true,
        // Remove unused code
        pure: isProduction ? ['console.log', 'console.info', 'console.debug'] : [],
        // Inline constants for better optimization
        define: isProduction ? {
          'process.env.NODE_ENV': '"production"',
          '__DEV__': 'false'
        } : {}
      }
    },
    
    // Performance optimizations
    optimizeDeps: {
      include: [
        'react',
        'react-dom',
        'react-router-dom',
        '@tanstack/react-query',
        'framer-motion',
        'lucide-react'
      ],
      // Force dependency pre-bundling for faster dev server startup
      force: false
    },
    
    // Define environment variables
    define: {
      __DEV__: !isProduction,
      __CI__: isCIBuild,
      'process.env.NODE_ENV': JSON.stringify(mode)
    },
    
    // CSS configuration
    css: {
      devSourcemap: !isProduction,
      postcss: './postcss.config.js'
    }
  }
})