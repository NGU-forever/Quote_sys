import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import globals from 'globals'
import skipFormatting from 'eslint-config-prettier'

export default [
  {
    name: 'app/files-to-lint',
    files: ['**/*.{js,mjs,cjs,vue}']
  },
  {
    name: 'app/files-to-ignore',
    ignores: [
      '**/dist/**',
      '**/dist-ssr/**',
      '**/release/**',
      '**/coverage/**',
      '**/node_modules/**',
      '**/visual-dist/**'
    ]
  },
  {
    name: 'app/main-process',
    files: ['electron/**/*.cjs'],
    languageOptions: {
      globals: globals.node,
      sourceType: 'commonjs'
    }
  },
  {
    name: 'app/browser-code',
    files: ['src/**/*.{js,vue}', 'vite.config.js', 'visual/**/*.js'],
    languageOptions: {
      globals: globals.browser
    }
  },
  {
    name: 'app/vite-config',
    files: ['vite.config.js', 'vite.visual.config.js'],
    languageOptions: {
      globals: globals.node
    }
  },
  {
    name: 'app/node-scripts',
    files: ['scripts/**/*.mjs', 'tests/**/*.mjs'],
    languageOptions: {
      globals: globals.node,
      sourceType: 'module'
    }
  },
  js.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  {
    name: 'app/rules',
    rules: {
      'vue/multi-word-component-names': ['error', { ignores: ['Panel'] }]
    }
  },
  skipFormatting
]
