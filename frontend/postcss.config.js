export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
    // Add CSS optimization for production builds
    ...(process.env.NODE_ENV === 'production' ? {
      cssnano: {
        preset: ['default', {
          discardComments: {
            removeAll: true,
          },
          normalizeWhitespace: true,
          minifyFontValues: true,
          minifySelectors: true,
        }]
      }
    } : {})
  },
}