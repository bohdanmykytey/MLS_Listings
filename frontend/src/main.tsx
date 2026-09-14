import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { CssBaseline, ThemeProvider, createTheme } from '@mui/material'
import App from './App'

// Minimal theme; visual polish isn't the point here.
const theme = createTheme({
  palette: { mode: 'light', background: { default: '#f7f8fa' } },
  shape: { borderRadius: 8 },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <App />
    </ThemeProvider>
  </StrictMode>,
)
