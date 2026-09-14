/**
 * The ranked result rows.
 *
 * Shows the four fields the brief requires (address, price, bedrooms,
 * relevance score) plus the score's two components, so a rank is explainable
 * at a glance rather than being an opaque number.
 *
 * Column sorting is deliberately **page-scoped**: clicking a header reorders
 * the rows already on screen, it does not re-query. That distinction matters
 * and is surfaced in the UI, because the two are easy to confuse — a
 * server-side "price ascending" would mean the cheapest listings overall,
 * whereas this means the current page's listings arranged by price. Relevance
 * still decides which listings reach the page at all; this only changes how
 * they are laid out once they are here.
 *
 * Done client-side because it needs no round trip and cannot desynchronise
 * pagination: the set of rows never changes, only their order.
 *
 * `showScore` hides the Score column entirely on an unfiltered search. With
 * no criteria entered there is nothing to be relevant *to* — every listing
 * ranks on time-on-market alone — so a number implying a considered rank
 * would be misleading rather than merely uninteresting.
 */

import { useMemo, useState } from 'react'
import {
  Chip,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  Tooltip,
  Typography,
} from '@mui/material'
import type { ScoredListing } from '../api/types'

/** Columns the user can reorder by, and how to read a value from a row. */
const SORTABLE = {
  address: (l: ScoredListing) => l.address,
  price: (l: ScoredListing) => l.price,
  bedrooms: (l: ScoredListing) => l.bedrooms,
  listedDate: (l: ScoredListing) => l.listedDate,
  relevanceScore: (l: ScoredListing) => l.relevanceScore,
} as const

type SortableColumn = keyof typeof SORTABLE
type SortDirection = 'asc' | 'desc'

const currency = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})

/**
 * Colour band for a relevance score.
 *
 * Thresholds are calibrated to the formula's realistic output range, not to a
 * naive 0-100 split. A perfect score needs both a price on the nose *and* a
 * listing at the far end of the negotiating window, which almost never
 * co-occur — across plausible budgets the top result lands in the 50-70 band
 * and the median nearer 15. Splitting at 70/40 would paint nearly every row
 * grey and tell the user nothing.
 */
function scoreColor(score: number): 'success' | 'warning' | 'default' {
  if (score >= 40) return 'success'
  if (score >= 20) return 'warning'
  return 'default'
}

export function ResultsTable({
  items,
  showScore = true,
}: {
  items: ScoredListing[]
  showScore?: boolean
}) {
  // `null` means "untouched": render exactly what the server sent, preserving
  // its ranking and its tie-break rather than re-deriving an order here.
  const [column, setColumn] = useState<SortableColumn | null>(null)
  const [direction, setDirection] = useState<SortDirection>('desc')

  const rows = useMemo(() => {
    if (column === null) return items
    const read = SORTABLE[column]
    return [...items].sort((a, b) => {
      const [x, y] = [read(a), read(b)]
      const cmp = x < y ? -1 : x > y ? 1 : 0
      if (cmp !== 0) return direction === 'asc' ? cmp : -cmp
      // Equal values fall back to the composite key. Not negated with the
      // direction: a tie-break exists to be stable, so flipping the column
      // must not reshuffle rows that were never distinguishable anyway.
      return a.key.localeCompare(b.key)
    })
  }, [items, column, direction])

  /** Clicking the active column flips direction; a new column starts descending. */
  const toggle = (next: SortableColumn) => {
    if (next === column) setDirection((d) => (d === 'asc' ? 'desc' : 'asc'))
    else {
      setColumn(next)
      setDirection('desc')
    }
  }

  const header = (key: SortableColumn, label: string) => (
    <TableSortLabel
      active={column === key}
      direction={column === key ? direction : 'desc'}
      onClick={() => toggle(key)}
    >
      {label}
    </TableSortLabel>
  )

  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>{header('address', 'Address')}</TableCell>
            <TableCell align="right">{header('price', 'Price')}</TableCell>
            <TableCell align="right">{header('bedrooms', 'Beds')}</TableCell>
            <TableCell>{header('listedDate', 'On market since')}</TableCell>
            {showScore && (
              <TableCell align="right">{header('relevanceScore', 'Score')}</TableCell>
            )}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((item) => (
            // Keyed by the composite source:id — `id` is not unique across feeds.
            <TableRow key={item.key} hover>
              <TableCell>
                <Typography variant="body2">{item.address}</Typography>
                <Stack direction="row" spacing={0.5} sx={{ mt: 0.5, alignItems: 'center', flexWrap: 'wrap' }}>
                  <Typography variant="caption" color="text.secondary">
                    {item.city}, {item.state} {item.zip} · {item.source}
                  </Typography>
                  {item.status !== 'active' && (
                    <Chip label={item.status} size="small" variant="outlined" />
                  )}
                  {item.mergedFrom.length > 0 && (
                    <Tooltip
                      title={
                        `Also listed as ${item.mergedFrom.join(', ')}. ` +
                        `On-market date is the earliest across those records.`
                      }
                    >
                      <Chip
                        label={`+${item.mergedFrom.length} duplicate`}
                        size="small"
                        color="info"
                        variant="outlined"
                      />
                    </Tooltip>
                  )}
                </Stack>
              </TableCell>
              <TableCell align="right">{currency.format(item.price)}</TableCell>
              <TableCell align="right">{item.bedrooms}</TableCell>
              <TableCell>{item.listedDate}</TableCell>
              {showScore && (
                <TableCell align="right">
                  <Tooltip
                    title={
                      `budget fit ${item.scoreBreakdown.budgetFit.toFixed(2)} ` +
                      `× ${item.scoreBreakdown.budgetWeight} + ` +
                      `negotiability ${item.scoreBreakdown.negotiability.toFixed(2)} ` +
                      `× ${item.scoreBreakdown.negotiabilityWeight}`
                    }
                  >
                    <Chip
                      label={item.relevanceScore.toFixed(1)}
                      size="small"
                      color={scoreColor(item.relevanceScore)}
                    />
                  </Tooltip>
                </TableCell>
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  )
}
