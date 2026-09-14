/**
 * The ranked result rows: address, price, bedrooms, and relevance score
 * (plus its two components in a tooltip), per the brief's minimum fields.
 *
 * Column sorting is page-scoped, client-side: it reorders the current page
 * only, it never re-queries — relevance still decides which rows reach the
 * page at all. Surfaced in the UI since it's easy to confuse with a
 * server-side sort over the whole result set.
 *
 * `showScore` can hide the Score column; unused today (the brief lists it as
 * always-shown) but kept as a tested prop.
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

/** Colour band calibrated to realistic scores, not a naive 0-100 split —
 *  a perfect 100 needs both a price on target and max negotiability, which
 *  rarely co-occur, so top results typically land around 50-70. */
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
  // null = untouched: render the server's own order/tie-break as-is.
  const [column, setColumn] = useState<SortableColumn | null>(null)
  const [direction, setDirection] = useState<SortDirection>('desc')

  const rows = useMemo(() => {
    if (column === null) return items
    const read = SORTABLE[column]
    return [...items].sort((a, b) => {
      const [x, y] = [read(a), read(b)]
      const cmp = x < y ? -1 : x > y ? 1 : 0
      if (cmp !== 0) return direction === 'asc' ? cmp : -cmp
      // Tie-break on key, never negated — direction shouldn't reshuffle ties.
      return a.key.localeCompare(b.key)
    })
  }, [items, column, direction])

  /** Active column flips direction; a new column starts descending. */
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
            // Composite key: `id` alone isn't unique across feeds.
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
