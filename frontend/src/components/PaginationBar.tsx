/**
 * Page controls plus the result count.
 *
 * MUI's Pagination is 1-indexed, matching the API, so no off-by-one
 * translation is needed. The count text is rendered from the server's
 * `pageInfo` rather than from `items.length`, so it describes the whole result
 * set and not just the visible page.
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
