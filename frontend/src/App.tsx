/**
 * Composition root: no search logic, just picks which state to render —
 * error, then loading, then empty, then results, in that precedence.
 */

import { useEffect, useState } from 'react'
import { Alert, Box, Container, Stack, Typography } from '@mui/material'
import { fetchCities } from './api/client'
import { useListingSearch } from './hooks/useListingSearch'
import { SearchForm } from './components/SearchForm'
import { ResultsTable } from './components/ResultsTable'
import { PaginationBar } from './components/PaginationBar'
import { EmptyView, ErrorView, LoadingView } from './components/StateViews'

export default function App() {
  const { form, data, loading, error, updateForm, runSearch, goToPage, reset, retry } =
    useListingSearch()

  // From the API so the dropdown reflects real data, not a stale hardcoded list.
  const [cities, setCities] = useState<string[]>([])
  const [citiesFailed, setCitiesFailed] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    fetchCities(controller.signal)
      .then(setCities)
      .catch(() => {
        if (!controller.signal.aborted) setCitiesFailed(true)
      })
    return () => controller.abort()
  }, [])

  const fieldIssues = error?.fieldIssues() ?? {}
  const hasResults = Boolean(data && data.items.length > 0)
  const isEmpty = Boolean(data && data.items.length === 0)

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" component="h1">
          Listing Search - By Bohdan Mykytey
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Filter and rank property listings ingested from multiple MLS feeds.
        </Typography>
      </Box>

      <Stack spacing={2}>
        {citiesFailed && (
          <Alert severity="info">
            Couldn't load the city list — you can still use every other filter.
          </Alert>
        )}

        <SearchForm
          form={form}
          cities={cities}
          fieldIssues={fieldIssues}
          onChange={updateForm}
          onSearch={runSearch}
          onReset={reset}
        />

        {error && <ErrorView error={error} onRetry={retry} />}
        {!error && loading && <LoadingView />}
        {!error && !loading && isEmpty && <EmptyView onReset={reset} />}
        {!error && !loading && hasResults && data && (
          <>
            <ResultsTable items={data.items} />
            <PaginationBar pageInfo={data.pageInfo} onChange={goToPage} />
          </>
        )}
      </Stack>
    </Container>
  )
}
