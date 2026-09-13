/**
 * Loading / empty / error views.
 *
 * The distinction under test is the one the brief calls out: a rejected query
 * and a query that simply matched nothing must not look the same.
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { EmptyView, ErrorView, LoadingView } from './StateViews'
import { ApiError } from '../api/client'

describe('LoadingView', () => {
  it('exposes an accessible loading indicator', () => {
    render(<LoadingView />)
    expect(screen.getByLabelText('Loading results')).toBeInTheDocument()
  })
})

describe('EmptyView', () => {
  it('says the search succeeded and nothing matched', () => {
    render(<EmptyView onReset={vi.fn()} />)
    expect(screen.getByText(/no listings match/i)).toBeInTheDocument()
    expect(screen.getByText(/ran successfully/i)).toBeInTheDocument()
  })

  it('offers a way out of an over-narrow filter set', async () => {
    const onReset = vi.fn()
    render(<EmptyView onReset={onReset} />)
    await userEvent.click(screen.getByRole('button', { name: /clear filters/i }))
    expect(onReset).toHaveBeenCalledOnce()
  })
})

describe('ErrorView', () => {
  const validationError = () =>
    new ApiError(400, {
      code: 'INVALID_REQUEST',
      message: 'One or more query parameters are invalid.',
      details: [{ field: null, issue: 'minPrice must be less than or equal to maxPrice' }],
    })

  const networkError = () =>
    new ApiError(0, { code: 'NETWORK_ERROR', message: 'Could not reach the search service.', details: [] })

  it('shows cross-field issues that belong to no single input', () => {
    render(<ErrorView error={validationError()} onRetry={vi.fn()} />)
    expect(screen.getByText(/minPrice must be less than or equal to maxPrice/)).toBeInTheDocument()
  })

  it('does not repeat field-level issues that the form already shows', () => {
    const error = new ApiError(400, {
      code: 'INVALID_REQUEST',
      message: 'One or more query parameters are invalid.',
      details: [{ field: 'pageSize', issue: 'Input should be greater than or equal to 1' }],
    })
    render(<ErrorView error={error} onRetry={vi.fn()} />)
    expect(screen.queryByText(/greater than or equal to 1/)).not.toBeInTheDocument()
  })

  it('frames a bad query as something to fix, not a failure', () => {
    render(<ErrorView error={validationError()} onRetry={vi.fn()} />)
    expect(screen.getByText(/check your filters/i)).toBeInTheDocument()
    // Retrying an invalid query would just fail again.
    expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument()
  })

  it('offers retry for a transport failure, which may be transient', async () => {
    const onRetry = vi.fn()
    render(<ErrorView error={networkError()} onRetry={onRetry} />)
    expect(screen.getByText(/search failed/i)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /retry/i }))
    expect(onRetry).toHaveBeenCalledOnce()
  })
})
