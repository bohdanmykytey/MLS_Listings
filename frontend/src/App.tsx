/**
 * Composition root: owns no search logic, just decides which state to render.
 *
 * The render branches are mutually exclusive and ordered by precedence —
 * error, then loading, then empty, then results — so the page can never show a
 * spinner over stale rows or an empty state next to an error.
 */

import { useEffect, useState } from 'react'
import { Alert, Box, Container, Stack, Typography } from '@mui/material'
import { fetchCities } from './api/client'
import { hasActiveFilters } from './api/searchState'
import { useListingSearch } from './hooks/useListingSearch'
import { SearchForm } from './components/SearchForm'
import { ResultsTable } from './components/ResultsTable'
import { PaginationBar } from './components/PaginationBar'
import { EmptyView, ErrorView, LoadingView } from './components/StateViews'

export default function App() {
  const { form, data, loading, error, updateForm, goToPage, reset, retry } =
    useListingSearch()

  // Cities come from the API so the dropdown reflects the real data rather
  // than a hardcoded list that silently rots.
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
  // No criteria entered means every listing ranks on time-on-market alone —
  // showing a relevance score for a ranking nobody asked for reads as noise.
  const showScore = hasActiveFilters(form)

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
          onReset={reset}
        />

        {error && <ErrorView error={error} onRetry={retry} />}
        {!error && loading && <LoadingView />}
        {!error && !loading && isEmpty && <EmptyView onReset={reset} />}
        {!error && !loading && hasResults && data && (
          <>
            <PaginationBar pageInfo={data.pageInfo} onChange={goToPage} />
            <ResultsTable items={data.items} showScore={showScore} />
            <PaginationBar pageInfo={data.pageInfo} onChange={goToPage} />
          </>
        )}
      </Stack>
    </Container>
  )
}
