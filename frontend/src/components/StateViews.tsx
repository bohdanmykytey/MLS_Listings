/**
 * Loading / empty / error views, kept separate so a rejected query (400)
 * reads as fixable, distinct from a valid query that matched nothing.
 */

import { Alert, AlertTitle, Box, Button, CircularProgress, Paper, Typography } from '@mui/material'
import type { ApiError } from '../api/client'

export function LoadingView() {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
      <CircularProgress aria-label="Loading results" />
    </Box>
  )
}

export function EmptyView({ onReset }: { onReset: () => void }) {
  return (
    <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
      <Typography variant="subtitle1" gutterBottom>
        No listings match these filters
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        The search ran successfully — the criteria are just too narrow.
      </Typography>
      <Button variant="outlined" size="small" onClick={onReset}>
        Clear filters
      </Button>
    </Paper>
  )
}

export function ErrorView({ error, onRetry }: { error: ApiError; onRetry: () => void }) {
  const general = error.generalIssues()
  // Field-level issues render on the inputs; no need to repeat them here.
  const isValidation = error.code === 'INVALID_REQUEST'

  return (
    <Alert
      severity={isValidation ? 'warning' : 'error'}
      action={
        isValidation ? undefined : (
          <Button color="inherit" size="small" onClick={onRetry}>
            Retry
          </Button>
        )
      }
    >
      <AlertTitle>{isValidation ? 'Check your filters' : 'Search failed'}</AlertTitle>
      <Typography variant="body2">{error.message}</Typography>
      {general.map((issue) => (
        <Typography key={issue} variant="body2" sx={{ mt: 0.5, fontWeight: 500 }}>
          · {issue}
        </Typography>
      ))}
    </Alert>
  )
}
