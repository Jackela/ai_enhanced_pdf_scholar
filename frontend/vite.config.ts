import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import { resolve } from 'path'

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
  
  // Get project root from environment variable or calculate from current directory
  const projectRoot = process.env.VITE_PROJECT_ROOT || resolve(__dirname, '..')
  const frontendSrcPath = resolve(projectRoot, 'frontend/src')

  return {
    plugins: [
      react({
        // Optimize React refresh for development
        fastRefresh: !isProduction,
        // Enable JSX runtime optimization
        jsxRuntime: 'automatic'
      }),
      VitePWA({
        registerType: 'autoUpdate',
        disable: isCIBuild, // Disable PWA plugin in CI to avoid path resolution conflicts
        workbox: {
          globPatterns: ['**/*.{js,css,html,ico,png,svg}'],
          // Enhanced caching for production
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
      
      rollupOptions: {
        // PWA-compatible path resolver with proper priority ordering
        plugins: [
          {
            name: 'ci-path-resolver',
            order: 'pre', // Critical: run before PWA plugin
            resolveId(id, importer) {
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
          // Enhanced chunk splitting for better caching
          manualChunks: {
            // Core React libraries
            'react-vendor': ['react', 'react-dom', 'react-router-dom'],
            
            // PDF processing libraries
            'pdf-vendor': ['pdfjs-dist', 'react-pdf'],
            
            // UI and animation libraries
            'ui-vendor': ['framer-motion', 'lucide-react', '@radix-ui/react-dropdown-menu', '@radix-ui/react-toast'],
            
            // State management and data fetching
            'state-vendor': ['@tanstack/react-query', '@tanstack/react-query-devtools', 'zustand'],
            
            // Utility libraries
            'utils-vendor': ['clsx', 'tailwind-merge', 'date-fns', 'axios']
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
          assetFileNames: 'assets/[name]-[hash].[ext]'
        },
        
        // Optimize external dependencies
        external: isProduction ? [] : ['react', 'react-dom']
      },
      
      // Build performance optimizations
      reportCompressedSize: !isCIBuild, // Skip compression reporting in CI for speed
      
      // Enhanced esbuild configuration
      esbuild: {
        // Remove console logs in production
        drop: isProduction ? ['console', 'debugger'] : [],
        // Optimize for faster builds in CI
        logOverride: isCIBuild ? { 'this-is-undefined-in-esm': 'silent' } : {}
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