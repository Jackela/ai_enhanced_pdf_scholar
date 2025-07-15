import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

// CI-optimized Vite configuration for faster, more reliable builds
export default defineConfig({
  plugins: [
    react({
      jsxRuntime: 'automatic',
      // Disable React refresh for CI builds
      fastRefresh: false,
    }),
  ],
  
  resolve: {
    alias: {
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
      '@/utils': resolve(__dirname, './src/utils'),
    },
    extensions: ['.ts', '.tsx', '.js', '.jsx', '.json', '.mjs'],
    preserveSymlinks: false,
  },
  
  build: {
    outDir: 'dist',
    // Disable source maps for faster CI builds
    sourcemap: false,
    // Use esbuild for faster minification
    minify: 'esbuild',
    target: 'es2020',
    // Increase chunk size limit to reduce warnings
    chunkSizeWarningLimit: 2000,
    // Disable CSS code splitting for simpler output
    cssCodeSplit: false,
    
    rollupOptions: {
      output: {
        // Simplified chunk splitting for CI
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          ui: ['framer-motion', 'lucide-react'],
          utils: ['clsx', 'tailwind-merge', 'date-fns'],
        },
        // Simple file naming for CI
        chunkFileNames: 'chunks/[name]-[hash].js',
        entryFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash].[ext]',
      },
    },
    
    // Optimize for CI performance
    reportCompressedSize: false,
    
    esbuild: {
      // Remove console logs and debugger statements
      drop: ['console', 'debugger'],
      // Minimize log output
      logOverride: {
        'this-is-undefined-in-esm': 'silent',
        'empty-import-meta': 'silent',
      },
    },
  },
  
  // Minimal optimizeDeps for faster startup
  optimizeDeps: {
    include: ['react', 'react-dom'],
    force: false,
  },
  
  // Define environment variables
  define: {
    __DEV__: false,
    __CI__: true,
    'process.env.NODE_ENV': '"production"',
  },
  
  // Minimal CSS processing for CI
  css: {
    devSourcemap: false,
    postcss: './postcss.config.js',
  },
  
  // Disable server features not needed in CI
  server: {
    hmr: false,
    open: false,
  },
})