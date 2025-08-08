/**
 * XSS Protection Utilities
 * 
 * Comprehensive security utilities for preventing Cross-Site Scripting (XSS) attacks
 * and ensuring safe content rendering throughout the application.
 * 
 * @security This module handles content sanitization and XSS prevention
 * @author AI Enhanced PDF Scholar Security Team
 * @version 2.1.0
 */

import DOMPurify from 'dompurify'
import { marked } from 'marked'

// Security configuration types
export interface SecurityConfig {
  allowMarkdown?: boolean
  allowImages?: boolean
  allowLinks?: boolean
  allowTables?: boolean
  allowCodeBlocks?: boolean
  allowBasicFormatting?: boolean
  stripAllHTML?: boolean
}

// XSS attack patterns to detect and prevent
const XSS_PATTERNS = {
  SCRIPT_TAGS: /<script[^>]*>[\s\S]*?<\/script>/gi,
  JAVASCRIPT_URLS: /javascript:[^"']*/gi,
  VBSCRIPT_URLS: /vbscript:[^"']*/gi,
  DATA_URLS_WITH_SCRIPT: /data:[^;]*;[^,]*,.*(<script|javascript:)/gi,
  EVENT_HANDLERS: /\son\w+\s*=\s*["'][^"']*["']/gi,
  STYLE_WITH_EXPRESSION: /style\s*=\s*["'][^"']*expression\s*\([^"']*["']/gi,
  IFRAME_TAGS: /<iframe[^>]*>[\s\S]*?<\/iframe>/gi,
  OBJECT_EMBED_TAGS: /<(object|embed)[^>]*>[\s\S]*?<\/(object|embed)>/gi,
  META_REFRESH: /<meta[^>]*http-equiv\s*=\s*["']?refresh["']?[^>]*>/gi,
  BASE_TAGS: /<base[^>]*>/gi,
  LINK_STYLESHEET: /<link[^>]*rel\s*=\s*["']?stylesheet["']?[^>]*>/gi,
}

// Safe HTML tags and attributes whitelist
const SAFE_TAGS = {
  BASIC_FORMATTING: ['b', 'i', 'u', 'em', 'strong', 'br', 'p', 'div', 'span'],
  LISTS: ['ul', 'ol', 'li'],
  HEADINGS: ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'],
  LINKS: ['a'],
  IMAGES: ['img'],
  TABLES: ['table', 'thead', 'tbody', 'tr', 'td', 'th'],
  CODE: ['code', 'pre', 'blockquote'],
  MARKDOWN_EXTRAS: ['hr', 'del', 'ins']
}

const SAFE_ATTRIBUTES = {
  GLOBAL: ['class', 'id'],
  LINKS: ['href', 'title', 'rel', 'target'],
  IMAGES: ['src', 'alt', 'width', 'height', 'title'],
  TABLES: ['colspan', 'rowspan'],
  CODE: ['class'] // For syntax highlighting
}

/**
 * DOMPurify configuration builder
 */
function createDOMPurifyConfig(options: SecurityConfig = {}) {
  const allowedTags = [...SAFE_TAGS.BASIC_FORMATTING]
  const allowedAttributes: { [key: string]: string[] } = {
    '*': SAFE_ATTRIBUTES.GLOBAL
  }

  // Build allowed tags based on options
  if (options.allowBasicFormatting !== false) {
    allowedTags.push(...SAFE_TAGS.LISTS, ...SAFE_TAGS.HEADINGS)
  }

  if (options.allowLinks) {
    allowedTags.push(...SAFE_TAGS.LINKS)
    allowedAttributes.a = SAFE_ATTRIBUTES.LINKS
  }

  if (options.allowImages) {
    allowedTags.push(...SAFE_TAGS.IMAGES)
    allowedAttributes.img = SAFE_ATTRIBUTES.IMAGES
  }

  if (options.allowTables) {
    allowedTags.push(...SAFE_TAGS.TABLES)
    Object.assign(allowedAttributes, {
      td: SAFE_ATTRIBUTES.TABLES,
      th: SAFE_ATTRIBUTES.TABLES
    })
  }

  if (options.allowCodeBlocks) {
    allowedTags.push(...SAFE_TAGS.CODE)
    allowedAttributes.code = SAFE_ATTRIBUTES.CODE
    allowedAttributes.pre = SAFE_ATTRIBUTES.CODE
  }

  if (options.allowMarkdown) {
    allowedTags.push(...SAFE_TAGS.MARKDOWN_EXTRAS)
  }

  return {
    ALLOWED_TAGS: allowedTags,
    ALLOWED_ATTR: allowedAttributes as any,
    KEEP_CONTENT: false,
    ALLOW_DATA_ATTR: false,
    ALLOW_UNKNOWN_PROTOCOLS: false,
    FORBID_TAGS: ['script', 'iframe', 'object', 'embed', 'form', 'input', 'textarea', 'button', 'link', 'style', 'meta', 'base'],
    FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover', 'onmouseout', 'onfocus', 'onblur', 'onchange', 'onsubmit', 'onreset', 'onkeydown', 'onkeyup', 'onkeypress'],
  }
}

/**
 * Sanitize text content by removing all HTML and potential XSS vectors
 */
export function sanitizeText(text: string): string {
  if (typeof text !== 'string') {
    return ''
  }

  // Remove all HTML tags and decode HTML entities
  const textOnly = DOMPurify.sanitize(text, { 
    ALLOWED_TAGS: [],
    ALLOWED_ATTR: [],
    KEEP_CONTENT: true 
  })

  // Additional cleaning for potential XSS vectors
  return textOnly
    .replace(/javascript:/gi, '')
    .replace(/vbscript:/gi, '')
    .replace(/data:/gi, '')
    .replace(/[\u0000-\u001F\u007F-\u009F]/g, '') // Remove control characters
    .trim()
}

/**
 * Sanitize HTML content with configurable security options
 */
export function sanitizeHTML(html: string, options: SecurityConfig = {}): string {
  if (typeof html !== 'string') {
    return ''
  }

  // If strip all HTML is requested, return text only
  if (options.stripAllHTML) {
    return sanitizeText(html)
  }

  const config = createDOMPurifyConfig(options)
  
  // Pre-processing: Remove known dangerous patterns
  let cleanHTML = html
  Object.values(XSS_PATTERNS).forEach(pattern => {
    cleanHTML = cleanHTML.replace(pattern, '')
  })

  // DOMPurify sanitization
  const sanitized = DOMPurify.sanitize(cleanHTML, config)

  // Post-processing: Additional security checks
  return postProcessSanitization(sanitized, options)
}

/**
 * Post-processing sanitization for additional security
 */
function postProcessSanitization(html: string, options: SecurityConfig): string {
  let processed = html

  // Ensure all links are secure
  if (options.allowLinks) {
    processed = processed.replace(/href\s*=\s*["']([^"']*)["']/gi, (_, url) => {
      const sanitizedUrl = sanitizeUrl(url)
      return `href="${sanitizedUrl}" rel="noopener noreferrer"`
    })
  }

  // Ensure all images have safe sources
  if (options.allowImages) {
    processed = processed.replace(/src\s*=\s*["']([^"']*)["']/gi, (_, url) => {
      const sanitizedUrl = sanitizeUrl(url)
      return `src="${sanitizedUrl}"`
    })
  }

  return processed
}

/**
 * Sanitize URLs to prevent JavaScript injection
 */
export function sanitizeUrl(url: string): string {
  if (typeof url !== 'string' || !url.trim()) {
    return '#'
  }

  const trimmed = url.trim().toLowerCase()

  // Block dangerous protocols
  const dangerousProtocols = ['javascript:', 'vbscript:', 'data:', 'file:', 'about:']
  for (const protocol of dangerousProtocols) {
    if (trimmed.startsWith(protocol)) {
      return '#'
    }
  }

  // Allow safe protocols
  const safeProtocols = ['http:', 'https:', 'mailto:', 'tel:', 'ftp:', '#']
  const hasProtocol = safeProtocols.some(protocol => 
    trimmed.startsWith(protocol) || (protocol === '#' && trimmed.startsWith('#'))
  )

  if (!hasProtocol && !trimmed.startsWith('/') && !trimmed.startsWith('./') && !trimmed.startsWith('../')) {
    // Relative URLs without explicit relative markers get https:// prefix
    return `https://${url}`
  }

  return url
}

/**
 * Sanitize markdown content and render it safely to HTML
 */
export function sanitizeAndRenderMarkdown(markdown: string, options: SecurityConfig = {}): string {
  if (typeof markdown !== 'string') {
    return ''
  }

  try {
    // Configure marked with security options
    marked.setOptions({
      breaks: true,
      gfm: true,
      silent: true, // Don't throw on malformed markdown
    })

    // Render markdown to HTML
    const html = marked(markdown) as string

    // Sanitize the resulting HTML
    return sanitizeHTML(html, {
      allowMarkdown: true,
      allowImages: options.allowImages || false,
      allowLinks: options.allowLinks !== false, // Default to true for markdown
      allowTables: options.allowTables !== false, // Default to true for markdown
      allowCodeBlocks: options.allowCodeBlocks !== false, // Default to true for markdown
      ...options
    })
  } catch (error) {
    console.warn('Markdown parsing error:', error)
    // Fallback to text sanitization
    return sanitizeText(markdown)
  }
}

/**
 * Detect potential XSS attempts in content
 */
export function detectXSSAttempt(content: string): { 
  isDetected: boolean
  patterns: string[]
  severity: 'low' | 'medium' | 'high' | 'critical'
} {
  if (typeof content !== 'string') {
    return { isDetected: false, patterns: [], severity: 'low' }
  }

  const detectedPatterns: string[] = []
  let highestSeverity: 'low' | 'medium' | 'high' | 'critical' = 'low'

  // Check for various XSS patterns
  const patternChecks = [
    { pattern: XSS_PATTERNS.SCRIPT_TAGS, name: 'Script Tags', severity: 'critical' as const },
    { pattern: XSS_PATTERNS.JAVASCRIPT_URLS, name: 'JavaScript URLs', severity: 'critical' as const },
    { pattern: XSS_PATTERNS.VBSCRIPT_URLS, name: 'VBScript URLs', severity: 'critical' as const },
    { pattern: XSS_PATTERNS.DATA_URLS_WITH_SCRIPT, name: 'Data URLs with Script', severity: 'critical' as const },
    { pattern: XSS_PATTERNS.EVENT_HANDLERS, name: 'Event Handlers', severity: 'high' as const },
    { pattern: XSS_PATTERNS.STYLE_WITH_EXPRESSION, name: 'CSS Expression', severity: 'high' as const },
    { pattern: XSS_PATTERNS.IFRAME_TAGS, name: 'IFrame Tags', severity: 'medium' as const },
    { pattern: XSS_PATTERNS.OBJECT_EMBED_TAGS, name: 'Object/Embed Tags', severity: 'medium' as const },
    { pattern: XSS_PATTERNS.META_REFRESH, name: 'Meta Refresh', severity: 'medium' as const },
    { pattern: XSS_PATTERNS.BASE_TAGS, name: 'Base Tags', severity: 'high' as const },
  ]

  patternChecks.forEach(({ pattern, name, severity }) => {
    if (pattern.test(content)) {
      detectedPatterns.push(name)
      if (severityLevel(severity) > severityLevel(highestSeverity)) {
        highestSeverity = severity
      }
    }
  })

  return {
    isDetected: detectedPatterns.length > 0,
    patterns: detectedPatterns,
    severity: highestSeverity
  }
}

function severityLevel(severity: 'low' | 'medium' | 'high' | 'critical'): number {
  const levels = { low: 1, medium: 2, high: 3, critical: 4 }
  return levels[severity]
}

/**
 * Escape HTML entities to prevent HTML injection
 */
export function escapeHTML(text: string): string {
  if (typeof text !== 'string') {
    return ''
  }

  const entityMap: { [key: string]: string } = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#x27;',
    '/': '&#x2F;',
    '`': '&#x60;',
    '=': '&#x3D;'
  }

  return text.replace(/[&<>"'`=\/]/g, char => entityMap[char])
}

/**
 * Content Security Policy (CSP) utilities
 */
export const CSP_POLICIES = {
  STRICT: {
    'default-src': "'self'",
    'script-src': "'self' 'unsafe-inline'", // Note: Consider removing 'unsafe-inline' for production
    'style-src': "'self' 'unsafe-inline' https://fonts.googleapis.com",
    'font-src': "'self' https://fonts.gstatic.com",
    'img-src': "'self' data: https:",
    'connect-src': "'self' ws: wss:",
    'frame-src': "'none'",
    'object-src': "'none'",
    'base-uri': "'self'",
    'form-action': "'self'",
    'frame-ancestors': "'none'"
  },
  MODERATE: {
    'default-src': "'self'",
    'script-src': "'self' 'unsafe-inline' 'unsafe-eval'",
    'style-src': "'self' 'unsafe-inline' https://fonts.googleapis.com",
    'font-src': "'self' https://fonts.gstatic.com https:",
    'img-src': "'self' data: https: http:",
    'connect-src': "'self' ws: wss: https: http:",
    'frame-src': "'self'",
    'object-src': "'none'",
    'base-uri': "'self'",
    'form-action': "'self'"
  }
}

/**
 * Generate CSP header string from policy object
 */
export function generateCSPHeader(policy: { [key: string]: string }): string {
  return Object.entries(policy)
    .map(([directive, value]) => `${directive} ${value}`)
    .join('; ')
}

/**
 * Validate and sanitize file uploads
 */
export interface FileValidationOptions {
  allowedTypes?: string[]
  maxSize?: number
  scanContent?: boolean
}

export function validateFile(file: File, options: FileValidationOptions = {}): {
  isValid: boolean
  errors: string[]
  sanitizedName: string
} {
  const errors: string[] = []
  
  // Sanitize filename
  const sanitizedName = file.name
    .replace(/[^a-zA-Z0-9.-]/g, '_')
    .replace(/_{2,}/g, '_')
    .substring(0, 255)

  // Check file type
  if (options.allowedTypes && !options.allowedTypes.includes(file.type)) {
    errors.push(`File type ${file.type} is not allowed`)
  }

  // Check file size
  if (options.maxSize && file.size > options.maxSize) {
    errors.push(`File size ${file.size} exceeds maximum of ${options.maxSize} bytes`)
  }

  // Check for dangerous file extensions
  const dangerousExtensions = ['.exe', '.bat', '.cmd', '.scr', '.vbs', '.js', '.jar', '.com', '.pif']
  const fileExtension = sanitizedName.toLowerCase().substring(sanitizedName.lastIndexOf('.'))
  if (dangerousExtensions.includes(fileExtension)) {
    errors.push(`File extension ${fileExtension} is not allowed`)
  }

  return {
    isValid: errors.length === 0,
    errors,
    sanitizedName
  }
}

// Export default security configuration
export const DEFAULT_SECURITY_CONFIG: SecurityConfig = {
  allowMarkdown: false,
  allowImages: false,
  allowLinks: false,
  allowTables: false,
  allowCodeBlocks: false,
  allowBasicFormatting: true,
  stripAllHTML: false
}

// Chat-specific security configuration
export const CHAT_SECURITY_CONFIG: SecurityConfig = {
  allowMarkdown: true,
  allowImages: false, // Disable images in chat for security
  allowLinks: true,
  allowTables: true,
  allowCodeBlocks: true,
  allowBasicFormatting: true,
  stripAllHTML: false
}