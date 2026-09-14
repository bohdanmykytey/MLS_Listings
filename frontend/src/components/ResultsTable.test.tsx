/**
 * The results table renders what the brief requires, and surfaces the extra
 * signals (duplicates, non-active status) that would otherwise be invisible.
 */

import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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

describe('column sorting (page-scoped)', () => {
  const threeRows = () => [
    makeListing({ key: 'MLS_A:A1', address: 'A house', price: 500000, relevanceScore: 90 }),
    makeListing({ key: 'MLS_A:A2', address: 'B house', price: 300000, relevanceScore: 70 }),
    makeListing({ key: 'MLS_A:A3', address: 'C house', price: 700000, relevanceScore: 80 }),
  ]

  /** The address line of each rendered row, in order, skipping the header. */
  const rendered = () =>
    screen
      .getAllByRole('row')
      .slice(1)
      .map((r) => within(r).getAllByRole('cell')[0].textContent?.split(/[A-Z][a-z]+,/)[0].trim())

  it('defaults to the order the server returned', () => {
    render(<ResultsTable items={threeRows()} />)
    expect(rendered()).toEqual(['A house', 'B house', 'C house'])
  })

  it('reorders by price when the price header is clicked', async () => {
    render(<ResultsTable items={threeRows()} />)
    await userEvent.click(screen.getByRole('button', { name: /price/i }))
    // First click is descending.
    expect(rendered()).toEqual(['C house', 'A house', 'B house'])
  })

  it('flips direction when the active column is clicked again', async () => {
    render(<ResultsTable items={threeRows()} />)
    const price = screen.getByRole('button', { name: /price/i })
    await userEvent.click(price)
    await userEvent.click(price)
    expect(rendered()).toEqual(['B house', 'A house', 'C house'])
  })

  it('never adds or drops rows — it only reorders them', async () => {
    // The property that makes page-scoped sorting safe alongside pagination.
    render(<ResultsTable items={threeRows()} />)
    const before = rendered().length
    await userEvent.click(screen.getByRole('button', { name: /beds/i }))
    expect(rendered()).toHaveLength(before)
  })

  it('orders equal values deterministically', async () => {
    const tied = [
      makeListing({ key: 'MLS_B:B2', address: 'Second', price: 400000 }),
      makeListing({ key: 'MLS_A:A1', address: 'First', price: 400000 }),
    ]
    render(<ResultsTable items={tied} />)
    await userEvent.click(screen.getByRole('button', { name: /price/i }))
    // Tied on price, so the composite key decides — stable across renders.
    expect(rendered()).toEqual(['First', 'Second'])
  })
})

describe('showScore', () => {
  it('shows the Score column by default', () => {
    render(<ResultsTable items={[makeListing()]} />)
    expect(screen.getByRole('columnheader', { name: /score/i })).toBeInTheDocument()
    expect(screen.getByText('89.0')).toBeInTheDocument()
  })

  it('hides the Score header and every score cell when showScore is false', () => {
    render(<ResultsTable items={[makeListing(), makeListing({ key: 'MLS_B:B7' })]} showScore={false} />)
    expect(screen.queryByRole('columnheader', { name: /score/i })).not.toBeInTheDocument()
    expect(screen.queryByText('89.0')).not.toBeInTheDocument()
  })

  it('still renders the required address, price, and bedrooms fields with the score hidden', () => {
    render(<ResultsTable items={[makeListing()]} showScore={false} />)
    expect(screen.getByText('123 Main St, Apt 4B')).toBeInTheDocument()
    expect(screen.getByText('$450,000')).toBeInTheDocument()
    const row = screen.getAllByRole('row')[1]
    expect(within(row).getByText('2')).toBeInTheDocument()
  })

  it('does not change the row count when the score column is hidden', () => {
    const items = [makeListing({ key: 'MLS_A:A1' }), makeListing({ key: 'MLS_B:B7' })]
    render(<ResultsTable items={items} showScore={false} />)
    expect(screen.getAllByRole('row')).toHaveLength(items.length + 1)
  })
})
