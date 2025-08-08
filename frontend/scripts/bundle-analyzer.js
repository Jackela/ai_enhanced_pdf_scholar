#!/usr/bin/env node

/**
 * Advanced Bundle Analyzer for AI Enhanced PDF Scholar Frontend
 * Provides detailed insights into bundle composition, size optimization, and performance metrics
 */

import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const distPath = path.join(__dirname, '../dist')

/**
 * Analyze bundle files and generate detailed report
 */
function analyzeBundles() {
  if (!fs.existsSync(distPath)) {
    console.error('❌ Distribution folder not found. Please run "npm run build" first.')
    process.exit(1)
  }

  console.log('🔍 AI Enhanced PDF Scholar - Bundle Analysis Report')
  console.log('=' .repeat(60))

  const assets = analyzePath(path.join(distPath, 'assets'))
  const chunks = analyzePath(path.join(distPath, 'chunks'))
  
  // Calculate totals
  const totalAssets = assets.reduce((sum, file) => sum + file.size, 0)
  const totalChunks = chunks.reduce((sum, file) => sum + file.size, 0)
  const totalSize = totalAssets + totalChunks

  // Main Bundle Analysis
  console.log('\n📦 MAIN BUNDLE ANALYSIS')
  console.log('-'.repeat(40))
  
  const mainJS = assets.find(f => f.name.startsWith('index-') && f.name.endsWith('.js'))
  const mainCSS = assets.find(f => f.name.startsWith('index-') && f.name.endsWith('.css'))
  
  if (mainJS) {
    const sizeStatus = mainJS.size > 300 * 1024 ? '🔴 OVER LIMIT' : '🟢 WITHIN LIMIT'
    console.log(`Main JS Bundle: ${formatSize(mainJS.size)} ${sizeStatus}`)
    console.log(`  Target: < 300KB | Current: ${((mainJS.size / (300 * 1024)) * 100).toFixed(1)}% of limit`)
  }
  
  if (mainCSS) {
    const sizeStatus = mainCSS.size > 50 * 1024 ? '🔴 OVER LIMIT' : '🟢 WITHIN LIMIT'  
    console.log(`Main CSS Bundle: ${formatSize(mainCSS.size)} ${sizeStatus}`)
    console.log(`  Target: < 50KB | Current: ${((mainCSS.size / (50 * 1024)) * 100).toFixed(1)}% of limit`)
  }

  // Chunk Analysis  
  console.log('\n🧩 CHUNK ANALYSIS')
  console.log('-'.repeat(40))
  
  const sortedChunks = chunks
    .filter(f => f.name.endsWith('.js'))
    .sort((a, b) => b.size - a.size)

  sortedChunks.forEach(chunk => {
    const category = categorizeChunk(chunk.name)
    const emoji = getCategoryEmoji(category)
    const status = getChunkStatus(chunk.name, chunk.size)
    
    console.log(`${emoji} ${chunk.name}`)
    console.log(`   Size: ${formatSize(chunk.size)} ${status}`)
    console.log(`   Category: ${category}`)
  })

  // Route-based Splitting Analysis
  console.log('\n🔀 ROUTE SPLITTING EFFICIENCY')
  console.log('-'.repeat(40))
  
  const routeChunks = chunks.filter(f => 
    f.name.includes('View-') || f.name.includes('Upload-')
  )
  
  const totalRouteSize = routeChunks.reduce((sum, chunk) => sum + chunk.size, 0)
  console.log(`Total Route Chunks: ${routeChunks.length}`)
  console.log(`Total Route Size: ${formatSize(totalRouteSize)}`)
  console.log(`Average Route Size: ${formatSize(totalRouteSize / routeChunks.length)}`)
  
  routeChunks.forEach(chunk => {
    const loadStrategy = getLoadStrategy(chunk.name)
    console.log(`  📄 ${chunk.name}: ${formatSize(chunk.size)} (${loadStrategy})`)
  })

  // Vendor Analysis
  console.log('\n📚 VENDOR CHUNK ANALYSIS')  
  console.log('-'.repeat(40))
  
  const vendorChunks = chunks.filter(f => 
    f.name.includes('vendor') || f.name.includes('react-') || f.name.includes('content-')
  ).sort((a, b) => b.size - a.size)
  
  vendorChunks.forEach(chunk => {
    const libraries = inferLibraries(chunk.name)
    const cachingStrategy = getCachingStrategy(chunk.name)
    console.log(`📦 ${chunk.name}: ${formatSize(chunk.size)}`)
    console.log(`   Libraries: ${libraries.join(', ')}`)
    console.log(`   Caching: ${cachingStrategy}`)
  })

  // Performance Metrics
  console.log('\n⚡ PERFORMANCE METRICS')
  console.log('-'.repeat(40))
  
  const metrics = calculateMetrics(mainJS, totalSize, chunks)
  console.log(`Initial Load Size: ${formatSize(metrics.initialLoad)}`)
  console.log(`Total App Size: ${formatSize(metrics.totalSize)}`)
  console.log(`Lazy Load Efficiency: ${metrics.lazyEfficiency}%`)
  console.log(`Cache Efficiency: ${metrics.cacheEfficiency}%`)
  
  // Performance Recommendations
  console.log('\n💡 OPTIMIZATION RECOMMENDATIONS')
  console.log('-'.repeat(40))
  
  const recommendations = generateRecommendations(chunks, mainJS, totalSize)
  recommendations.forEach(rec => console.log(`${rec.priority} ${rec.message}`))

  // Summary
  console.log('\n📊 BUNDLE SUMMARY')  
  console.log('-'.repeat(40))
  console.log(`Total Files: ${assets.length + chunks.length}`)
  console.log(`Total Size: ${formatSize(totalSize)}`)
  console.log(`Main Bundle: ${formatSize(mainJS?.size || 0)} (${((mainJS?.size || 0) / totalSize * 100).toFixed(1)}%)`)
  console.log(`Lazy Loaded: ${formatSize(totalSize - (mainJS?.size || 0))} (${(((totalSize - (mainJS?.size || 0)) / totalSize) * 100).toFixed(1)}%)`)
  
  console.log('\n✅ Bundle analysis complete!')
  
  // Generate JSON report for CI
  const report = {
    timestamp: new Date().toISOString(),
    mainBundle: {
      js: mainJS?.size || 0,
      css: mainCSS?.size || 0
    },
    chunks: sortedChunks.map(c => ({ name: c.name, size: c.size })),
    metrics,
    recommendations: recommendations.map(r => ({ priority: r.priority, message: r.message }))
  }
  
  fs.writeFileSync(
    path.join(distPath, 'bundle-analysis.json'),
    JSON.stringify(report, null, 2)
  )
  console.log(`📄 Detailed report saved to: dist/bundle-analysis.json`)
}

/**
 * Analyze files in a directory
 */
function analyzePath(dirPath) {
  if (!fs.existsSync(dirPath)) return []
  
  return fs.readdirSync(dirPath)
    .filter(file => file.endsWith('.js') || file.endsWith('.css'))
    .map(file => {
      const filePath = path.join(dirPath, file)
      const stats = fs.statSync(filePath)
      return {
        name: file,
        size: stats.size,
        path: filePath
      }
    })
}

/**
 * Format file size in human readable format
 */
function formatSize(bytes) {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

/**
 * Categorize chunks by their content
 */
function categorizeChunk(filename) {
  if (filename.includes('View-')) return 'Route Component'
  if (filename.includes('Upload-')) return 'Feature Component'
  if (filename.includes('react-')) return 'React Framework'
  if (filename.includes('vendor')) return 'Third Party Library'
  if (filename.includes('utils-')) return 'Utility Functions'
  if (filename.includes('content-')) return 'Content Processing'
  return 'Application Code'
}

/**
 * Get category emoji
 */
function getCategoryEmoji(category) {
  const emojis = {
    'Route Component': '🏠',
    'Feature Component': '🔧', 
    'React Framework': '⚛️',
    'Third Party Library': '📦',
    'Utility Functions': '🛠️',
    'Content Processing': '📝',
    'Application Code': '💼'
  }
  return emojis[category] || '📄'
}

/**
 * Get chunk size status
 */
function getChunkStatus(filename, size) {
  if (filename.includes('react-core') && size > 150 * 1024) return '⚠️'
  if (filename.includes('vendor') && size > 100 * 1024) return '⚠️'  
  if (filename.includes('View-') && size > 80 * 1024) return '⚠️'
  if (size > 200 * 1024) return '🔴'
  if (size > 100 * 1024) return '🟡'
  return '🟢'
}

/**
 * Get loading strategy for chunk
 */
function getLoadStrategy(filename) {
  if (filename.includes('View-')) return 'Route-based lazy loading'
  if (filename.includes('Upload-')) return 'On-demand loading'
  return 'Bundled with app'
}

/**
 * Infer libraries in vendor chunks
 */
function inferLibraries(filename) {
  const libraryMap = {
    'react-core': ['React', 'React-DOM'],
    'react-router': ['React Router'],
    'vendor': ['Framer Motion', 'Lucide Icons', 'Various'],
    'content-vendor': ['Marked', 'DOMPurify', 'React Markdown'],
    'utils-vendor': ['Clsx', 'Tailwind Merge', 'Date-fns'],
  }
  
  for (const [key, libs] of Object.entries(libraryMap)) {
    if (filename.includes(key)) return libs
  }
  
  return ['Unknown']
}

/**
 * Get caching strategy recommendation
 */
function getCachingStrategy(filename) {
  if (filename.includes('react-')) return 'Long-term (framework stable)'
  if (filename.includes('vendor')) return 'Long-term (vendor libs stable)'
  if (filename.includes('utils-')) return 'Medium-term (utils change occasionally)'
  return 'Short-term (app code changes frequently)'
}

/**
 * Calculate performance metrics
 */
function calculateMetrics(mainJS, totalSize, chunks) {
  const initialLoad = mainJS?.size || 0
  const lazyLoadedSize = totalSize - initialLoad
  const lazyEfficiency = ((lazyLoadedSize / totalSize) * 100).toFixed(1)
  
  // Calculate cache efficiency based on vendor chunk sizes
  const vendorSize = chunks
    .filter(c => c.name.includes('vendor') || c.name.includes('react-'))
    .reduce((sum, c) => sum + c.size, 0)
  const cacheEfficiency = ((vendorSize / totalSize) * 100).toFixed(1)
  
  return {
    initialLoad,
    totalSize,
    lazyEfficiency,
    cacheEfficiency
  }
}

/**
 * Generate optimization recommendations
 */
function generateRecommendations(chunks, mainJS, totalSize) {
  const recommendations = []
  
  // Check main bundle size
  if (mainJS && mainJS.size > 250 * 1024) {
    recommendations.push({
      priority: '🔴 HIGH',
      message: `Main bundle (${formatSize(mainJS.size)}) approaching 300KB limit. Consider more aggressive code splitting.`
    })
  }
  
  // Check large chunks
  const largeChunks = chunks.filter(c => c.size > 100 * 1024)
  if (largeChunks.length > 0) {
    recommendations.push({
      priority: '🟡 MEDIUM', 
      message: `${largeChunks.length} chunks exceed 100KB. Consider splitting: ${largeChunks.map(c => c.name).join(', ')}`
    })
  }
  
  // Check vendor consolidation
  const vendorChunks = chunks.filter(c => c.name.includes('vendor'))
  if (vendorChunks.length > 5) {
    recommendations.push({
      priority: '🟡 MEDIUM',
      message: `${vendorChunks.length} vendor chunks detected. Consider consolidating rarely-changed libraries.`
    })
  }
  
  // Check route splitting efficiency
  const routeChunks = chunks.filter(c => c.name.includes('View-'))
  const avgRouteSize = routeChunks.reduce((sum, c) => sum + c.size, 0) / routeChunks.length
  if (avgRouteSize > 50 * 1024) {
    recommendations.push({
      priority: '🟢 LOW',
      message: `Average route chunk size (${formatSize(avgRouteSize)}) is optimal. Good code splitting!`
    })
  }
  
  // Success metrics
  if (mainJS && mainJS.size < 30 * 1024) {
    recommendations.push({
      priority: '✅ EXCELLENT',
      message: `Main bundle size (${formatSize(mainJS.size)}) is exceptional! Great lazy loading implementation.`
    })
  }
  
  if (recommendations.length === 0) {
    recommendations.push({
      priority: '✅ EXCELLENT',
      message: 'Bundle optimization is excellent! No immediate improvements needed.'
    })
  }
  
  return recommendations
}

// Run the analyzer
if (import.meta.url === `file://${process.argv[1]}`) {
  analyzeBundles()
}

export { analyzeBundles }