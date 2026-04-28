import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// Force SODA theme — runs after CSS loads, before React renders.
// This overrides any CopilotKit CSS variable no matter how it was injected.
const html = document.documentElement
html.setAttribute('data-theme', 'dark')
html.classList.add('dark')

const vars = {
  '--copilot-kit-background-color':        '#000000',
  '--copilot-kit-secondary-color':         '#0a0a0a',
  '--copilot-kit-primary-color':           '#e040fb',
  '--copilot-kit-contrast-color':          '#ffffff',
  '--copilot-kit-secondary-contrast-color':'#ffffff',
  '--copilot-kit-muted-color':             '#546e7a',
  '--copilot-kit-separator-color':         '#1a1a1a',
  '--copilot-kit-input-background-color':  '#050505',
  '--copilot-kit-error-background':        '#1a0000',
  '--copilot-kit-error-border':            '#ff1744',
  '--copilot-kit-error-text':              '#ff5252',
}
for (const [k, v] of Object.entries(vars)) {
  html.style.setProperty(k, v)
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
