/**
 * The ranked result rows.
 *
 * Shows the four fields the brief requires (address, price, bedrooms,
 * relevance score) plus the score's two components, so a rank is explainable
 * at a glance rather than being an opaque number.
 */

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
  Tooltip,
  Typography,
} from '@mui/material'
import type { ScoredListing } from '../api/types'

const currency = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})

/** Green at 100, amber mid-range, grey at the bottom. */
function scoreColor(score: number): 'success' | 'warning' | 'default' {
  if (score >= 70) return 'success'
  if (score >= 40) return 'warning'
  return 'default'
}

export function ResultsTable({ items }: { items: ScoredListing[] }) {
  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Address</TableCell>
            <TableCell align="right">Price</TableCell>
            <TableCell align="right">Beds</TableCell>
            <TableCell>Listed</TableCell>
            <TableCell align="right">Score</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {items.map((item) => (
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
                    <Tooltip title={`Also listed as ${item.mergedFrom.join(', ')}`}>
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
              <TableCell align="right">
                <Tooltip
                  title={
                    `budget fit ${item.scoreBreakdown.budgetFit.toFixed(2)} ` +
                    `× ${item.scoreBreakdown.budgetWeight} + ` +
                    `recency ${item.scoreBreakdown.recency.toFixed(2)} ` +
                    `× ${item.scoreBreakdown.recencyWeight}`
                  }
                >
                  <Chip
                    label={item.relevanceScore.toFixed(1)}
                    size="small"
                    color={scoreColor(item.relevanceScore)}
                  />
                </Tooltip>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  )
}
