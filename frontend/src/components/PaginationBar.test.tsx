/**
 * The pager, and the count text that describes the whole result set rather
 * than the visible page.
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { PaginationBar } from './PaginationBar'
import { makePageInfo } from '../test/factories'

describe('PaginationBar', () => {
  it('describes the current slice of the full result set', () => {
    render(<PaginationBar pageInfo={makePageInfo({ page: 2 })} onChange={vi.fn()} />)
    expect(screen.getByText(/Showing 6–10 of 12 listings/)).toBeInTheDocument()
  })

  it('reports a short final page correctly', () => {
    render(<PaginationBar pageInfo={makePageInfo({ page: 3 })} onChange={vi.fn()} />)
    expect(screen.getByText(/Showing 11–12 of 12 listings/)).toBeInTheDocument()
  })

  it('reports an empty result set as 0 rather than as 1–0', () => {
    const info = makePageInfo({ page: 1, total: 0, totalPages: 0 })
    render(<PaginationBar pageInfo={info} onChange={vi.fn()} />)
    expect(screen.getByText(/Showing 0–0 of 0 listings/)).toBeInTheDocument()
  })

  it('uses the singular for exactly one result', () => {
    const info = makePageInfo({ total: 1, totalPages: 1 })
    render(<PaginationBar pageInfo={info} onChange={vi.fn()} />)
    expect(screen.getByText(/of 1 listing$/)).toBeInTheDocument()
  })

  it('hides the pager when everything fits on one page', () => {
    const info = makePageInfo({ total: 3, totalPages: 1 })
    render(<PaginationBar pageInfo={info} onChange={vi.fn()} />)
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  })

  it('moves to the page the user clicks', async () => {
    const onChange = vi.fn()
    render(<PaginationBar pageInfo={makePageInfo()} onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: /go to page 3/i }))
    expect(onChange).toHaveBeenCalledWith(3)
  })
})
