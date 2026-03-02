import js from '@eslint/js'

/** @type {import('eslint').Linter.Config[]} */
export default [
  js.configs.recommended,
  {
    rules: {
      'no-console': ['warn', { allow: ['warn', 'error'] }],
      'no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      'prefer-const': 'error',
      'no-var': 'error',
    },
  },
  {
    ignores: ['dist/**', '.next/**', 'node_modules/**'],
  },
]
