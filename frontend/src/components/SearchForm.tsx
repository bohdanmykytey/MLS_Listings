/**
 * The filter inputs. Editing only updates the draft; wrapped in a real
 * <form> so Enter submits like any other search box. Server-side validation
 * errors map back onto the offending field via `ApiError.fieldIssues()`.
 */

import {
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  IconButton,
  InputAdornment,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import ClearIcon from '@mui/icons-material/Clear'
import SearchIcon from '@mui/icons-material/Search'
import type { SearchFormState } from '../api/types'

interface Props {
  form: SearchFormState
  cities: string[]
  fieldIssues: Record<string, string>
  onChange: (patch: Partial<SearchFormState>) => void
  onSearch: () => void
  onReset: () => void
}

export function SearchForm({ form, cities, fieldIssues, onChange, onSearch, onReset }: Props) {
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault() // stop the browser's default form navigation
    onSearch()
  }

  /** Per-field clear button; only rendered once there's something to clear. */
  const clearAdornment = (name: keyof SearchFormState, label: string) =>
    form[name]
      ? {
          endAdornment: (
            <InputAdornment position="end">
              <IconButton
                size="small"
                edge="end"
                aria-label={`Clear ${label.toLowerCase()}`}
                onClick={() => onChange({ [name]: '' } as Partial<SearchFormState>)}
              >
                <ClearIcon fontSize="inherit" />
              </IconButton>
            </InputAdornment>
          ),
        }
      : {}

  /** Shared props for a numeric text input, incl. server-side issue text. */
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
    slotProps: { input: clearAdornment(name, label) },
  })

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="subtitle2" color="text.secondary" gutterBottom>
        Filters
      </Typography>

      <Stack component="form" onSubmit={handleSubmit} noValidate spacing={1.5}>
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
            slotProps={{ input: clearAdornment('keyword', 'Keyword in description') }}
          />
        </Stack>

        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
          <TextField
            {...numeric('targetBudget', 'Target budget', 'Drives 60% of the relevance score')}
          />
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
                  // Tooltip wrapper leaves no associated <label>; name it explicitly.
                  slotProps={{ input: { 'aria-label': 'Merge duplicates across feeds' } }}
                />
              }
              label="Merge duplicates across feeds"
            />
          </Tooltip>
          <Stack direction="row" spacing={1}>
            {/* type="button": inside a <form>, the default type is "submit". */}
            <Button type="button" onClick={onReset} size="small">
              Reset
            </Button>
            <Button type="submit" variant="contained" size="small" startIcon={<SearchIcon />}>
              Search
            </Button>
          </Stack>
        </Box>
      </Stack>
    </Paper>
  )
}
