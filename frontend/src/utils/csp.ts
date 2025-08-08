/**
 * Content Security Policy (CSP) Configuration
 * 
 * Provides CSP header generation and policy management for enhanced security
 * against XSS attacks, code injection, and other web vulnerabilities.
 * 
 * @security CSP headers for preventing script injection and XSS attacks
 * @author AI Enhanced PDF Scholar Security Team
 * @version 2.1.0
 */

/**
 * CSP Policy Configurations
 */
export const CSP_DIRECTIVES = {
  // Production-ready strict policy
  PRODUCTION: {
    'default-src': "'self'",
    'script-src': "'self'",
    'style-src': "'self' 'unsafe-inline' https://fonts.googleapis.com",
    'font-src': "'self' https://fonts.gstatic.com",
    'img-src': "'self' data: https:",
    'connect-src': "'self' ws://localhost:8000 wss://localhost:8000",
    'frame-src': "'none'",
    'object-src': "'none'",
    'base-uri': "'self'",
    'form-action': "'self'",
    'frame-ancestors': "'none'",
    'upgrade-insecure-requests': "",
    'block-all-mixed-content': ""
  },

  // Development policy with relaxed restrictions for debugging
  DEVELOPMENT: {
    'default-src': "'self'",
    'script-src': "'self' 'unsafe-inline' 'unsafe-eval'", // Allow eval for HMR
    'style-src': "'self' 'unsafe-inline' https://fonts.googleapis.com",
    'font-src': "'self' https://fonts.gstatic.com https:",
    'img-src': "'self' data: https: http:",
    'connect-src': "'self' ws: wss: http://localhost:* https://localhost:*",
    'frame-src': "'self'",
    'object-src': "'none'",
    'base-uri': "'self'",
    'form-action': "'self'"
  },

  // Testing environment policy
  TESTING: {
    'default-src': "'self'",
    'script-src': "'self' 'unsafe-inline' 'unsafe-eval'", // Allow unsafe for test frameworks
    'style-src': "'self' 'unsafe-inline'",
    'font-src': "'self' data:",
    'img-src': "'self' data:",
    'connect-src': "'self'",
    'frame-src': "'none'",
    'object-src': "'none'",
    'base-uri': "'self'",
    'form-action': "'self'"
  },

  // Strict security policy for high-risk environments
  STRICT: {
    'default-src': "'none'",
    'script-src': "'self'",
    'style-src': "'self' https://fonts.googleapis.com",
    'font-src': "https://fonts.gstatic.com",
    'img-src': "'self' data:",
    'connect-src': "'self'",
    'frame-src': "'none'",
    'object-src': "'none'",
    'base-uri': "'none'",
    'form-action': "'none'",
    'frame-ancestors': "'none'",
    'upgrade-insecure-requests': "",
    'block-all-mixed-content': "",
    'require-sri-for': "script style"
  }
}

/**
 * Generate CSP header string from policy object
 */
export function generateCSPHeader(policy: { [key: string]: string }): string {
  return Object.entries(policy)
    .filter(([_, value]) => value !== undefined)
    .map(([directive, value]) => 
      value ? `${directive} ${value}` : directive
    )
    .join('; ')
}

/**
 * Get appropriate CSP policy based on environment
 */
export function getCSPPolicy(environment: string = process.env.NODE_ENV || 'development'): { [key: string]: string } {
  switch (environment.toLowerCase()) {
    case 'production':
      return CSP_DIRECTIVES.PRODUCTION
    case 'test':
    case 'testing':
      return CSP_DIRECTIVES.TESTING
    case 'strict':
      return CSP_DIRECTIVES.STRICT
    case 'development':
    default:
      return CSP_DIRECTIVES.DEVELOPMENT
  }
}

/**
 * CSP Violation Report Handler
 */
export interface CSPViolation {
  'document-uri': string
  referrer: string
  'blocked-uri': string
  'violated-directive': string
  'effective-directive': string
  'original-policy': string
  disposition: 'enforce' | 'report'
  'script-sample': string
  'status-code': number
  'source-file': string
  'line-number': number
  'column-number': number
}

/**
 * Handle CSP violation reports
 */
export function handleCSPViolation(violation: CSPViolation): void {
  console.error('CSP Violation:', {
    directive: violation['violated-directive'],
    blockedUri: violation['blocked-uri'],
    sourceFile: violation['source-file'],
    lineNumber: violation['line-number'],
    columnNumber: violation['column-number'],
    sample: violation['script-sample']
  })

  // In production, send to monitoring service
  if (process.env.NODE_ENV === 'production') {
    // TODO: Send to monitoring service (e.g., Sentry, LogRocket)
    // fetch('/api/security/csp-violation', {
    //   method: 'POST',
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify(violation)
    // })
  }
}

/**
 * Setup CSP violation event listener
 */
export function setupCSPViolationListener(): void {
  if (typeof window !== 'undefined') {
    document.addEventListener('securitypolicyviolation', (event) => {
      handleCSPViolation({
        'document-uri': event.documentURI,
        referrer: event.referrer,
        'blocked-uri': event.blockedURI,
        'violated-directive': event.violatedDirective,
        'effective-directive': event.effectiveDirective,
        'original-policy': event.originalPolicy,
        disposition: event.disposition as 'enforce' | 'report',
        'script-sample': event.sample,
        'status-code': event.statusCode,
        'source-file': event.sourceFile,
        'line-number': event.lineNumber,
        'column-number': event.columnNumber
      })
    })
  }
}

/**
 * Create CSP meta tag for client-side implementation
 */
export function createCSPMetaTag(policy?: { [key: string]: string }): HTMLMetaElement | null {
  if (typeof window === 'undefined') return null

  const cspPolicy = policy || getCSPPolicy()
  const cspHeader = generateCSPHeader(cspPolicy)

  // Remove existing CSP meta tag
  const existingCSP = document.querySelector('meta[http-equiv="Content-Security-Policy"]')
  if (existingCSP) {
    existingCSP.remove()
  }

  // Create new CSP meta tag
  const meta = document.createElement('meta')
  meta.httpEquiv = 'Content-Security-Policy'
  meta.content = cspHeader

  return meta
}

/**
 * Apply CSP policy to document
 */
export function applyCSPPolicy(policy?: { [key: string]: string }): void {
  const metaTag = createCSPMetaTag(policy)
  if (metaTag && typeof document !== 'undefined') {
    document.head.appendChild(metaTag)
    console.info('CSP Policy Applied:', policy || getCSPPolicy())
  }
}

/**
 * Validate CSP policy configuration
 */
export function validateCSPPolicy(policy: { [key: string]: string }): {
  isValid: boolean
  warnings: string[]
  errors: string[]
} {
  const warnings: string[] = []
  const errors: string[] = []

  // Check for dangerous configurations
  if (policy['script-src']?.includes("'unsafe-eval'")) {
    warnings.push("'unsafe-eval' in script-src allows dangerous eval() usage")
  }

  if (policy['script-src']?.includes("'unsafe-inline'")) {
    warnings.push("'unsafe-inline' in script-src allows inline scripts")
  }

  if (policy['style-src']?.includes("'unsafe-inline'")) {
    warnings.push("'unsafe-inline' in style-src allows inline styles")
  }

  if (policy['default-src'] === "'none'" && !policy['script-src']) {
    errors.push("default-src 'none' requires explicit script-src directive")
  }

  if (policy['object-src'] && policy['object-src'] !== "'none'") {
    warnings.push("object-src should be 'none' to prevent Flash/plugin exploits")
  }

  if (!policy['base-uri']) {
    warnings.push("base-uri directive missing - consider adding 'self' or 'none'")
  }

  if (!policy['frame-ancestors']) {
    warnings.push("frame-ancestors directive missing - consider adding 'none' to prevent clickjacking")
  }

  return {
    isValid: errors.length === 0,
    warnings,
    errors
  }
}

/**
 * CSP Nonce Generator
 */
export class CSPNonceManager {
  private static instance: CSPNonceManager
  private nonces: Map<string, string> = new Map()

  static getInstance(): CSPNonceManager {
    if (!CSPNonceManager.instance) {
      CSPNonceManager.instance = new CSPNonceManager()
    }
    return CSPNonceManager.instance
  }

  generateNonce(prefix: string = 'script'): string {
    const array = new Uint8Array(16)
    crypto.getRandomValues(array)
    const nonce = Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('')
    this.nonces.set(prefix, nonce)
    return nonce
  }

  getNonce(prefix: string = 'script'): string | undefined {
    return this.nonces.get(prefix)
  }

  clearNonces(): void {
    this.nonces.clear()
  }
}

// Initialize CSP violation listener
if (typeof window !== 'undefined') {
  setupCSPViolationListener()
}

export default {
  CSP_DIRECTIVES,
  generateCSPHeader,
  getCSPPolicy,
  applyCSPPolicy,
  validateCSPPolicy,
  setupCSPViolationListener,
  CSPNonceManager
}