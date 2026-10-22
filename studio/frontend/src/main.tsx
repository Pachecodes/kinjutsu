import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './App'
import { ToastProvider } from './components/ui/toast'
import { TooltipProvider } from './components/ui/tooltip'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5_000,
    },
  },
})

const container = document.getElementById('root')
if (!container) throw new Error('Missing #root element')

createRoot(container).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={220} skipDelayDuration={400}>
        <ToastProvider>
          <App />
        </ToastProvider>
      </TooltipProvider>
    </QueryClientProvider>
  </StrictMode>,
)
