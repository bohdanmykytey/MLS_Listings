/**
 * The filter inputs.
 *
 * Server-side validation errors are mapped back onto the specific field that
 * caused them (via `ApiError.fieldIssues()`), so a rejected query points at
 * the input to fix instead of showing a banner and leaving the user guessing.
 */

import {
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import type { SearchFormState, SortOption } from '../api/types'

const SORT_LABELS: Record<SortOption, string> = {
  relevance: 'Relevance',
  priceAsc: 'Price: low to high',
  priceDesc: 'Price: high to low',
  newest: 'Newest first',
}

interface Props {
  form: SearchFormState
  cities: string[]
  fieldIssues: Record<string, string>
  onChange: (patch: Partial<SearchFormState>) => void
  onReset: () => void
}

export function SearchForm({ form, cities, fieldIssues, onChange, onReset }: Props) {
  /** Shared props for a numeric text input, including any server-side issue. */
  const numeric = (name: keyof SearchFormState, label: string, helper?: string) => ({
    label,
    value: String(form[name]),
    onChange: (e: React.ChangeEvent<HTMLInputElement>) =>
      onChange({ [name]: e.target.value } as Partial<SearchFormState>),
    error: Boolean(fieldIssues[name]),
    helperText: fieldIssues[name] ?? helper ?? ' ',
    type: 'number' as const,
    size: 'small' as const,
    fullWidth: true,
  })

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="subtitle2" color="text.secondary" gutterBottom>
        Filters
      </Typography>

      <Stack spacing={1.5}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
          <TextField {...numeric('minPrice', 'Min price')} />
          <TextField {...numeric('maxPrice', 'Max price')} />
          <TextField {...numeric('minBedrooms', 'Min bedrooms')} />
        </Stack>

        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
          <TextField
            select
            label="City"
            size="small"
            fullWidth
            value={form.city}
            onChange={(e) => onChange({ city: e.target.value })}
            error={Boolean(fieldIssues.city)}
            helperText={fieldIssues.city ?? ' '}
          >
            <MenuItem value="">Any city</MenuItem>
            {cities.map((city) => (
              <MenuItem key={city} value={city}>
                {city}
              </MenuItem>
            ))}
          </TextField>

          <TextField
            label="Keyword in description"
            size="small"
            fullWidth
            value={form.keyword}
            placeholder="e.g. garage, kitchen"
            onChange={(e) => onChange({ keyword: e.target.value })}
            error={Boolean(fieldIssues.keyword)}
            helperText={fieldIssues.keyword ?? ' '}
          />
        </Stack>

        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
          <TextField
            {...numeric('targetBudget', 'Target budget', 'Drives 60% of the relevance score')}
          />
          <TextField
            select
            label="Sort by"
            size="small"
            fullWidth
            value={form.sort}
            helperText=" "
            onChange={(e) => onChange({ sort: e.target.value as SortOption })}
          >
            {Object.entries(SORT_LABELS).map(([value, label]) => (
              <MenuItem key={value} value={value}>
                {label}
              </MenuItem>
            ))}
          </TextField>
          <TextField {...numeric('pageSize', 'Results per page')} />
        </Stack>

        <Box
          sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
        >
          <Tooltip title="Collapse records from different feeds that describe the same property, matched on coordinates, bedrooms and sqft.">
            <FormControlLabel
              control={
                <Checkbox
                  checked={form.dedupe}
                  onChange={(e) => onChange({ dedupe: e.target.checked })}
                  // Explicit: the surrounding Tooltip leaves the input without
                  // an associated <label>, so screen readers would otherwise
                  // announce an unnamed checkbox.
                  slotProps={{ input: { 'aria-label': 'Merge duplicates across feeds' } }}
                />
              }
              label="Merge duplicates across feeds"
            />
          </Tooltip>
          <Button onClick={onReset} size="small">
            Reset
          </Button>
        </Box>
      </Stack>
    </Paper>
  )
}
