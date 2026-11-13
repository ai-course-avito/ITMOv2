import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from 'next-themes'
import './index.css'
import App from './App'
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { AuthProvider } from '@/lib/auth'
import { ensureLocalePrefix } from '@/lib/i18n'
import { queryClient } from '@/lib/queries'

// The panel used to keep the users it had seen in the browser; the service lists them now (GET /users/recent). Drop what was kept.
try {
  Object.keys(localStorage).filter((k) => k.startsWith('omnixon.recentUsers.')).forEach((k) => localStorage.removeItem(k))
} catch {
  /* storage may be unavailable */
}

// an address without its language (`/chat`) is sent to the same page with one (`/ru/chat`); the page then loads again
if (ensureLocalePrefix()) {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
        <QueryClientProvider client={queryClient}>
          <TooltipProvider>
            <AuthProvider>
              <App />
            </AuthProvider>
            <Toaster richColors position="bottom-right" />
          </TooltipProvider>
        </QueryClientProvider>
      </ThemeProvider>
    </StrictMode>,
  )
}
