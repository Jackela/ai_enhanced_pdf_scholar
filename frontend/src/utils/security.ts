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
  SCRIPT_TAGS: /<script[^>]*>[\s\S]*?<\/script>|<script[^>]*>/gi,
  JAVASCRIPT_URLS: /javascript:[^"']*/gi,
  VBSCRIPT_URLS: /vbscript:[^"']*/gi,
  DATA_URLS_WITH_SCRIPT: /data:[^;]*;[^,]*,.*(<script|javascript:)/gi,
  EVENT_HANDLERS: /\s?on\w+\s*=\s*[^>\s]*/gi,
  STYLE_WITH_EXPRESSION: /style\s*=\s*["'][^"']*expression\s*\([^"']*["']/gi,
  IFRAME_TAGS: /<iframe[^>]*>[\s\S]*?<\/iframe>|<iframe[^>]*>/gi,
  OBJECT_EMBED_TAGS: /<(object|embed)[^>]*>[\s\S]*?<\/(object|embed)>/gi,
  META_REFRESH: /<meta[^>]*http-equiv\s*=\s*["']?refresh["']?[^>]*>/gi,
  BASE_TAGS: /<base[^>]*>/gi,
  LINK_STYLESHEET: /<link[^>]*rel\s*=\s*["']?stylesheet["']?[^>]*>/gi,
  // HTML entity encoded patterns
  ENCODED_JAVASCRIPT: /&#[0-9]+;/gi, // Basic pattern for HTML entities - will check decoded content
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
  const allowedAttributes: { [key: string]: string[] } = {}

  // Always allow global attributes on all elements
  allowedTags.forEach(tag => {
    allowedAttributes[tag] = [...SAFE_ATTRIBUTES.GLOBAL]
  })

  // Build allowed tags based on options
  if (options.allowBasicFormatting !== false) {
    const additionalTags = [...SAFE_TAGS.LISTS, ...SAFE_TAGS.HEADINGS]
    allowedTags.push(...additionalTags)
    additionalTags.forEach(tag => {
      allowedAttributes[tag] = [...SAFE_ATTRIBUTES.GLOBAL]
    })
  }

  if (options.allowLinks) {
    allowedTags.push(...SAFE_TAGS.LINKS)
    allowedAttributes.a = [...SAFE_ATTRIBUTES.GLOBAL, ...SAFE_ATTRIBUTES.LINKS]
  }

  if (options.allowImages) {
    allowedTags.push(...SAFE_TAGS.IMAGES)
    allowedAttributes.img = [...SAFE_ATTRIBUTES.GLOBAL, ...SAFE_ATTRIBUTES.IMAGES]
  }

  if (options.allowTables) {
    allowedTags.push(...SAFE_TAGS.TABLES)
    SAFE_TAGS.TABLES.forEach(tag => {
      allowedAttributes[tag] = [...SAFE_ATTRIBUTES.GLOBAL, ...(SAFE_ATTRIBUTES.TABLES || [])]
    })
  }

  if (options.allowCodeBlocks) {
    allowedTags.push(...SAFE_TAGS.CODE)
    SAFE_TAGS.CODE.forEach(tag => {
      allowedAttributes[tag] = [...SAFE_ATTRIBUTES.GLOBAL, ...SAFE_ATTRIBUTES.CODE]
    })
  }

  if (options.allowMarkdown) {
    allowedTags.push(...SAFE_TAGS.MARKDOWN_EXTRAS)
    SAFE_TAGS.MARKDOWN_EXTRAS.forEach(tag => {
      allowedAttributes[tag] = [...SAFE_ATTRIBUTES.GLOBAL]
    })
  }

  // Build list of forbidden tags, excluding allowed ones
  const forbiddenTags = ['script', 'iframe', 'object', 'embed', 'form', 'input', 'textarea', 'button', 'link', 'style', 'meta', 'base']
  if (options.allowLinks) {
    const linkIndex = forbiddenTags.indexOf('link')
    if (linkIndex > -1) forbiddenTags.splice(linkIndex, 1)
  }

  // Create a flat list of all allowed attributes
  const allAllowedAttributes = new Set<string>()
  Object.values(allowedAttributes).forEach(attrs => {
    attrs.forEach(attr => allAllowedAttributes.add(attr))
  })

  const dompurifyConfig: any = {
    ALLOWED_TAGS: allowedTags,
    ALLOWED_ATTR: Array.from(allAllowedAttributes),
    KEEP_CONTENT: true, // Keep text content even if tags are removed
    ALLOW_DATA_ATTR: false,
    FORBID_TAGS: forbiddenTags,
    FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover', 'onmouseout', 'onfocus', 'onblur', 'onchange', 'onsubmit', 'onreset', 'onkeydown', 'onkeyup', 'onkeypress'],
    ALLOW_UNKNOWN_PROTOCOLS: false
  }

  return dompurifyConfig
}

/**
 * Sanitize text content by removing all HTML and potential XSS vectors
 */
export function sanitizeText(text: string): string {
  if (typeof text !== 'string') {
    return ''
  }

  // First pass: remove dangerous tags but preserve inner content
  let cleaned = text
    .replace(/<script[^>]*>([\s\S]*?)<\/script>/gi, '$1') // Keep script content as text
    .replace(/<[^>]+>/g, '') // Remove all HTML tags
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#x27;/g, "'") // Decode basic entities

  // Remove dangerous protocol prefixes but preserve the rest
  cleaned = cleaned
    .replace(/javascript:\s*/gi, '') // Remove javascript: protocol but keep following text
    .replace(/vbscript:\s*/gi, '') // Remove vbscript: protocol but keep following text
    // eslint-disable-next-line no-control-regex
    .replace(/[\u0000-\u001F\u007F-\u009F]/g, '') // Remove control characters (intentional for security)
    .trim()

  return cleaned
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

  // DOMPurify sanitization - let it handle most of the work
  const sanitized = DOMPurify.sanitize(html, config)

  // Post-processing: Additional security checks
  let processedSanitized = postProcessSanitization(sanitized.toString(), options)

  // Final pass: remove any remaining dangerous protocols that might have escaped
  processedSanitized = processedSanitized.replace(/javascript:\s*/gi, '').replace(/vbscript:\s*/gi, '')

  return processedSanitized
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

  // Decode HTML entities to check for encoded XSS - handle various formats including malformed ones
  const decodedContent = content
    // Handle standard decimal entities with semicolon (&#106; or &#0000106;)
    .replace(/&#0*(\d+);/g, (_, dec) => {
      const num = parseInt(dec, 10)
      return num > 0 && num < 1114112 ? String.fromCharCode(num) : ''
    })
    // Handle malformed decimal entities without semicolon in img tags and similar contexts
    .replace(/&#0*(\d+)(?=[^0-9;]|$)/g, (_, dec) => {
      const num = parseInt(dec, 10)
      return num > 0 && num < 1114112 ? String.fromCharCode(num) : ''
    })
    // Handle hex entities
    .replace(/&#x([0-9a-f]+);/gi, (_, hex) => {
      const num = parseInt(hex, 16)
      return num > 0 && num < 1114112 ? String.fromCharCode(num) : ''
    })
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')

  // Check for various XSS patterns in both original and decoded content
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
    // Reset regex lastIndex to ensure consistent matching
    pattern.lastIndex = 0
    // Check both original and decoded content
    if (pattern.test(content) || pattern.test(decodedContent)) {
      detectedPatterns.push(name)
      if (severityLevel(severity) > severityLevel(highestSeverity)) {
        highestSeverity = severity
      }
    }
  })

  // Additional check for encoded patterns - check if content has HTML entities at all
  if (content.includes('&#') || content.includes('&')) {
    // Check if decoded content contains dangerous patterns
    const decodedLower = decodedContent.toLowerCase()
    if (decodedLower.includes('javascript:') ||
        decodedLower.includes('vbscript:') ||
        decodedLower.includes('alert') ||
        decodedLower.includes('<script') ||
        decodedLower.includes('onerror') ||
        decodedLower.includes('onload')) {
      detectedPatterns.push('HTML Entity Encoded XSS')
      if (severityLevel('critical') > severityLevel(highestSeverity)) {
        highestSeverity = 'critical'
      }
    }

    // Additional check: look for dangerous tags with external sources
    if ((decodedLower.includes('<img') || decodedLower.includes('<iframe') || decodedLower.includes('<script')) && (
        decodedLower.includes('javascript:') ||
        decodedLower.includes('vbscript:') ||
        decodedLower.includes('onerror') ||
        decodedLower.includes('src=http'))) {
      detectedPatterns.push('External Resource XSS')
      if (severityLevel('critical') > severityLevel(highestSeverity)) {
        highestSeverity = 'critical'
      }
    }
  }

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

  return text.replace(/[&<>"'`=/]/g, char => entityMap[char])
}

/**
 * Content Security Policy (CSP) utilities
 */
export const CSP_POLICIES = {
  STRICT: {
    'default-src': "'none'",
    'script-src': "'self'",
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
    .filter(([_, value]) => value !== undefined && value !== null)
    .map(([directive, value]) => value === '' ? directive : `${directive} ${value}`)
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
