#!/usr/bin/env node

/**
 * Bundle Size Regression Check for CI/CD Pipeline
 * Ensures bundle sizes stay within performance budgets
 */

const fs = require('fs')
const path = require('path')

const distPath = path.join(__dirname, '../dist')

// Performance budgets (in bytes)
const BUDGETS = {
  mainBundle: 300 * 1024,      // 300KB - critical for performance
  cssBundle: 50 * 1024,        // 50KB - styling limit
  routeChunk: 100 * 1024,      // 100KB - per route limit
  vendorChunk: 200 * 1024,     // 200KB - per vendor chunk limit
  totalInitialLoad: 400 * 1024 // 400KB - total initial load limit
}

// Warning thresholds (80% of budget)
const WARNING_THRESHOLDS = {
  mainBundle: BUDGETS.mainBundle * 0.8,
  cssBundle: BUDGETS.cssBundle * 0.8,
  routeChunk: BUDGETS.routeChunk * 0.8,
  vendorChunk: BUDGETS.vendorChunk * 0.8,
  totalInitialLoad: BUDGETS.totalInitialLoad * 0.8
}

function formatSize(bytes) {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

function getPercentage(current, budget) {
  return ((current / budget) * 100).toFixed(1)
}

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

function checkBundleSizes() {
  if (!fs.existsSync(distPath)) {
    console.error('❌ Distribution folder not found. Please run "npm run build" first.')
    process.exit(1)
  }

  console.log('🔍 Bundle Size Check - Performance Budget Validation')
  console.log('=' .repeat(60))

  const assets = analyzePath(path.join(distPath, 'assets'))
  const chunks = analyzePath(path.join(distPath, 'chunks'))
  
  let hasErrors = false
  let hasWarnings = false

  // Check main bundle
  console.log('\n📦 Main Bundle Check')
  console.log('-'.repeat(30))
  
  const mainJS = assets.find(f => f.name.startsWith('index-') && f.name.endsWith('.js'))
  const mainCSS = assets.find(f => f.name.startsWith('index-') && f.name.endsWith('.css'))
  
  if (mainJS) {
    const percentage = getPercentage(mainJS.size, BUDGETS.mainBundle)
    const status = mainJS.size > BUDGETS.mainBundle ? '❌ OVER BUDGET' : 
                   mainJS.size > WARNING_THRESHOLDS.mainBundle ? '⚠️ WARNING' : '✅ OK'
    
    console.log(`Main JS: ${formatSize(mainJS.size)} / ${formatSize(BUDGETS.mainBundle)} (${percentage}%) ${status}`)
    
    if (mainJS.size > BUDGETS.mainBundle) {
      hasErrors = true
      console.log(`  💥 CRITICAL: Main bundle exceeds 300KB limit by ${formatSize(mainJS.size - BUDGETS.mainBundle)}`)
    } else if (mainJS.size > WARNING_THRESHOLDS.mainBundle) {
      hasWarnings = true
      console.log(`  ⚠️  WARNING: Main bundle is at ${percentage}% of 300KB limit`)
    }
  }
  
  if (mainCSS) {
    const percentage = getPercentage(mainCSS.size, BUDGETS.cssBundle)
    const status = mainCSS.size > BUDGETS.cssBundle ? '❌ OVER BUDGET' : 
                   mainCSS.size > WARNING_THRESHOLDS.cssBundle ? '⚠️ WARNING' : '✅ OK'
    
    console.log(`Main CSS: ${formatSize(mainCSS.size)} / ${formatSize(BUDGETS.cssBundle)} (${percentage}%) ${status}`)
    
    if (mainCSS.size > BUDGETS.cssBundle) {
      hasErrors = true
      console.log(`  💥 CRITICAL: CSS bundle exceeds 50KB limit by ${formatSize(mainCSS.size - BUDGETS.cssBundle)}`)
    } else if (mainCSS.size > WARNING_THRESHOLDS.cssBundle) {
      hasWarnings = true
      console.log(`  ⚠️  WARNING: CSS bundle is at ${percentage}% of 50KB limit`)
    }
  }

  // Check route chunks
  console.log('\n🏠 Route Chunks Check')
  console.log('-'.repeat(30))
  
  const routeChunks = chunks.filter(f => f.name.includes('View-') || f.name.includes('Upload-'))
  
  routeChunks.forEach(chunk => {
    const percentage = getPercentage(chunk.size, BUDGETS.routeChunk)
    const status = chunk.size > BUDGETS.routeChunk ? '❌ OVER BUDGET' : 
                   chunk.size > WARNING_THRESHOLDS.routeChunk ? '⚠️ WARNING' : '✅ OK'
    
    console.log(`${chunk.name}: ${formatSize(chunk.size)} / ${formatSize(BUDGETS.routeChunk)} (${percentage}%) ${status}`)
    
    if (chunk.size > BUDGETS.routeChunk) {
      hasErrors = true
      console.log(`  💥 CRITICAL: Route chunk exceeds 100KB limit by ${formatSize(chunk.size - BUDGETS.routeChunk)}`)
    } else if (chunk.size > WARNING_THRESHOLDS.routeChunk) {
      hasWarnings = true
      console.log(`  ⚠️  WARNING: Route chunk is at ${percentage}% of 100KB limit`)
    }
  })

  // Check vendor chunks
  console.log('\n📦 Vendor Chunks Check')
  console.log('-'.repeat(30))
  
  const vendorChunks = chunks.filter(f => 
    f.name.includes('vendor') || f.name.includes('react-') || f.name.includes('content-')
  )
  
  vendorChunks.forEach(chunk => {
    const percentage = getPercentage(chunk.size, BUDGETS.vendorChunk)
    const status = chunk.size > BUDGETS.vendorChunk ? '❌ OVER BUDGET' : 
                   chunk.size > WARNING_THRESHOLDS.vendorChunk ? '⚠️ WARNING' : '✅ OK'
    
    console.log(`${chunk.name}: ${formatSize(chunk.size)} / ${formatSize(BUDGETS.vendorChunk)} (${percentage}%) ${status}`)
    
    if (chunk.size > BUDGETS.vendorChunk) {
      hasErrors = true
      console.log(`  💥 CRITICAL: Vendor chunk exceeds 200KB limit by ${formatSize(chunk.size - BUDGETS.vendorChunk)}`)
    } else if (chunk.size > WARNING_THRESHOLDS.vendorChunk) {
      hasWarnings = true
      console.log(`  ⚠️  WARNING: Vendor chunk is at ${percentage}% of 200KB limit`)
    }
  })

  // Check total initial load
  console.log('\n⚡ Initial Load Check')
  console.log('-'.repeat(30))
  
  const initialLoadSize = (mainJS?.size || 0) + (mainCSS?.size || 0)
  const percentage = getPercentage(initialLoadSize, BUDGETS.totalInitialLoad)
  const status = initialLoadSize > BUDGETS.totalInitialLoad ? '❌ OVER BUDGET' : 
                 initialLoadSize > WARNING_THRESHOLDS.totalInitialLoad ? '⚠️ WARNING' : '✅ OK'
  
  console.log(`Initial Load: ${formatSize(initialLoadSize)} / ${formatSize(BUDGETS.totalInitialLoad)} (${percentage}%) ${status}`)
  
  if (initialLoadSize > BUDGETS.totalInitialLoad) {
    hasErrors = true
    console.log(`  💥 CRITICAL: Initial load exceeds 400KB limit by ${formatSize(initialLoadSize - BUDGETS.totalInitialLoad)}`)
  } else if (initialLoadSize > WARNING_THRESHOLDS.totalInitialLoad) {
    hasWarnings = true
    console.log(`  ⚠️  WARNING: Initial load is at ${percentage}% of 400KB limit`)
  }

  // Summary
  console.log('\n📊 Size Check Summary')
  console.log('-'.repeat(30))
  
  if (hasErrors) {
    console.log('❌ FAILED: Bundle size check failed - performance budget exceeded')
    console.log('\n💡 Optimization suggestions:')
    console.log('  - Review route-based code splitting')
    console.log('  - Check for unnecessary dependencies')
    console.log('  - Consider lazy loading more components')
    console.log('  - Analyze bundle composition with npm run analyze')
    process.exit(1)
  } else if (hasWarnings) {
    console.log('⚠️  WARNING: Bundle sizes approaching limits')
    console.log('\n💡 Consider proactive optimizations:')
    console.log('  - Monitor bundle growth in future PRs')
    console.log('  - Consider further code splitting')
    console.log('  - Review dependency usage')
    process.exit(0) // Don't fail CI for warnings
  } else {
    console.log('✅ PASSED: All bundle sizes within performance budgets')
    console.log('🚀 Performance optimization status: EXCELLENT')
    console.log('\n📈 Current efficiency:')
    console.log(`  - Main bundle: ${formatSize(mainJS?.size || 0)} (${getPercentage(mainJS?.size || 0, BUDGETS.mainBundle)}% of budget)`)
    console.log(`  - Initial load: ${formatSize(initialLoadSize)} (${percentage}% of budget)`)
    console.log(`  - Route chunks: ${routeChunks.length} properly split`)
    console.log(`  - Vendor chunks: ${vendorChunks.length} optimally cached`)
  }
}

// Run the check
checkBundleSizes()