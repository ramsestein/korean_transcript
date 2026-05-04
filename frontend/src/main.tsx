import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'

// Debug: log immediately to verify JS is running
console.log('main.tsx: starting React app...')

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
