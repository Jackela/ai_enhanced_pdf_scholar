import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import { resolve } from 'path'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const isProduction = mode === 'production'
  const isCIBuild = env.CI === 'true'

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
      })
    ],
    resolve: {
      alias: {
        // Enhanced alias configuration for reliable CI/CD path resolution
        '@': resolve(__dirname, './src'),
        '@/lib': resolve(__dirname, './src/lib'),
        '@/lib/api': resolve(__dirname, './src/lib/api.ts'),
        '@/lib/utils': resolve(__dirname, './src/lib/utils.ts'),
        '@/components': resolve(__dirname, './src/components'),
        '@/pages': resolve(__dirname, './src/pages'),
        '@/hooks': resolve(__dirname, './src/hooks'),
        '@/services': resolve(__dirname, './src/services'),
        '@/store': resolve(__dirname, './src/store'),
        '@/types': resolve(__dirname, './src/types'),
        '@/utils': resolve(__dirname, './src/utils')
      },
      // Improve module resolution reliability across environments
      extensions: ['.ts', '.tsx', '.js', '.jsx', '.json', '.mjs'],
      // Ensure consistent module resolution in CI
      preserveSymlinks: false
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