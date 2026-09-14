/**
 * Page controls plus the result count. Driven by the server's `pageInfo`,
 * not `items.length`, so the count describes the whole result set.
 */

import { Pagination, Stack, Typography } from '@mui/material'
import type { PageInfo } from '../api/types'

interface Props {
  pageInfo: PageInfo
  onChange: (page: number) => void
}

export function PaginationBar({ pageInfo, onChange }: Props) {
  const { page, pageSize, total, totalPages } = pageInfo
  const first = total === 0 ? 0 : (page - 1) * pageSize + 1
  const last = Math.min(page * pageSize, total)

  return (
    <Stack
      direction={{ xs: 'column', sm: 'row' }}
      spacing={1}
      sx={{ alignItems: 'center', justifyContent: 'space-between' }}
    >
      <Typography variant="body2" color="text.secondary">
        Showing {first}–{last} of {total} {total === 1 ? 'listing' : 'listings'}
        {total > 0 && ' · ranked by relevance; column sorting reorders this page only'}
      </Typography>
      {totalPages > 1 && (
        <Pagination
          count={totalPages}
          page={page}
          onChange={(_, next) => onChange(next)}
          size="small"
          color="primary"
          showFirstButton
          showLastButton
        />
      )}
    </Stack>
  )
}
