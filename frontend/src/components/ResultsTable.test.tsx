/**
 * The results table renders what the brief requires, and surfaces the extra
 * signals (duplicates, non-active status) that would otherwise be invisible.
 */

import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ResultsTable } from './ResultsTable'
import { makeListing } from '../test/factories'

describe('ResultsTable', () => {
  it('renders the four fields the brief requires', () => {
    render(<ResultsTable items={[makeListing()]} />)
    expect(screen.getByText('123 Main St, Apt 4B')).toBeInTheDocument()  // address
    expect(screen.getByText('$450,000')).toBeInTheDocument()             // price
    expect(screen.getByText('89.0')).toBeInTheDocument()                 // score
    const row = screen.getAllByRole('row')[1]
    expect(within(row).getByText('2')).toBeInTheDocument()               // bedrooms
  })

  it('formats price as currency rather than a raw number', () => {
    render(<ResultsTable items={[makeListing({ price: 1234567 })]} />)
    expect(screen.getByText('$1,234,567')).toBeInTheDocument()
    expect(screen.queryByText('1234567')).not.toBeInTheDocument()
  })

  it('renders one row per listing', () => {
    const items = [
      makeListing({ key: 'MLS_A:A1', id: 'A1' }),
      makeListing({ key: 'MLS_B:B7', id: 'B7', address: '123 Main Street, Unit 4B' }),
      makeListing({ key: 'MLS_A:A2', id: 'A2', address: '456 Oak Ave' }),
    ]
    render(<ResultsTable items={items} />)
    expect(screen.getAllByRole('row')).toHaveLength(items.length + 1) // + header
  })

  it('keys rows by the composite source:id so cross-feed id collisions render', () => {
    // A1 from two different feeds: keying on `id` alone would collide.
    const items = [
      makeListing({ key: 'MLS_A:A1', id: 'A1', source: 'MLS_A' }),
      makeListing({ key: 'MLS_B:A1', id: 'A1', source: 'MLS_B', address: '999 Other St' }),
    ]
    render(<ResultsTable items={items} />)
    expect(screen.getAllByRole('row')).toHaveLength(3)
    expect(screen.getByText('999 Other St')).toBeInTheDocument()
  })

  it('flags a row that absorbed duplicates', () => {
    render(<ResultsTable items={[makeListing({ mergedFrom: ['MLS_B:B7'] })]} />)
    expect(screen.getByText('+1 duplicate')).toBeInTheDocument()
  })

  it('shows no duplicate chip when nothing was merged', () => {
    render(<ResultsTable items={[makeListing({ mergedFrom: [] })]} />)
    expect(screen.queryByText(/duplicate/)).not.toBeInTheDocument()
  })

  it('flags a non-active listing but not an active one', () => {
    const { rerender } = render(<ResultsTable items={[makeListing({ status: 'pending' })]} />)
    expect(screen.getByText('pending')).toBeInTheDocument()
    rerender(<ResultsTable items={[makeListing({ status: 'active' })]} />)
    expect(screen.queryByText('active')).not.toBeInTheDocument()
  })

  it('renders an empty table body without crashing', () => {
    render(<ResultsTable items={[]} />)
    expect(screen.getAllByRole('row')).toHaveLength(1) // header only
  })
})
