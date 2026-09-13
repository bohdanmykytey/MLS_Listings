/**
 * End-to-end behaviour of the page against a mocked API.
 *
 * These are the tests that would catch the bugs a user actually hits: a stale
 * page number after changing a filter, a spinner that never clears, an error
 * that leaves old rows on screen. `fetch` is stubbed rather than the client,
 * so the real query-building and error-parsing code runs.
 */

import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { makeListing, makePageInfo, makeResponse } from './test/factories'

const CITIES = ['Fairfax', 'Reston', 'Springfield']

/** URLs of every search request made, in order. */
let searchUrls: string[] = []

/** The page number a request asked for, so the mock can answer faithfully. */
function pageOf(url: string): number {
  return Number(new URLSearchParams(url.split('?')[1]).get('page') ?? 1)
}

function mockApi(
  // The default echoes the requested page back in `pageInfo`; a mock that
  // always claimed page 1 would leave the pager showing the wrong current page.
  handler: (url: string) => { status?: number; body: unknown } = (url) => ({
    body: makeResponse({ pageInfo: makePageInfo({ page: pageOf(url) }) }),
  }),
) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url.startsWith('/api/cities')) {
        return new Response(JSON.stringify(CITIES), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      searchUrls.push(url)
      const { status = 200, body } = handler(url)
      return new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json' },
      })
    }),
  )
}

/** The query parameters of the most recent search request. */
function lastQuery(): URLSearchParams {
  return new URLSearchParams(searchUrls[searchUrls.length - 1].split('?')[1])
}

beforeEach(() => {
  searchUrls = []
  // jsdom keeps one window for the whole file, and the app now reads its
  // initial state from the URL — so without this, each test would inherit the
  // previous test's search.
  window.history.replaceState(null, '', '/')
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('initial load', () => {
  it('shows a loading indicator before results arrive', () => {
    mockApi()
    render(<App />)
    expect(screen.getByLabelText('Loading results')).toBeInTheDocument()
  })

  it('renders ranked results once loaded', async () => {
    mockApi()
    render(<App />)
    expect(await screen.findByText('123 Main St, Apt 4B')).toBeInTheDocument()
    expect(screen.getByText('$450,000')).toBeInTheDocument()
  })

  it('clears the loading indicator when results arrive', async () => {
    mockApi()
    render(<App />)
    await screen.findByText('123 Main St, Apt 4B')
    expect(screen.queryByLabelText('Loading results')).not.toBeInTheDocument()
  })

  it('populates the city dropdown from the API', async () => {
    mockApi()
    render(<App />)
    await screen.findByText('123 Main St, Apt 4B')
    await userEvent.click(screen.getByRole('combobox', { name: /city/i }))
    for (const city of CITIES) {
      expect(screen.getByRole('option', { name: city })).toBeInTheDocument()
    }
  })
})

describe('empty and error states', () => {
  it('shows the empty state, not an error, when nothing matches', async () => {
    mockApi(() => ({
      body: makeResponse({ items: [], pageInfo: { page: 1, pageSize: 5, total: 0, totalPages: 0 } }),
    }))
    render(<App />)
    expect(await screen.findByText(/no listings match/i)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows a validation error and drops stale rows', async () => {
    mockApi(() => ({
      status: 400,
      body: {
        error: {
          code: 'INVALID_REQUEST',
          message: 'One or more query parameters are invalid.',
          details: [{ field: null, issue: 'minPrice must be less than or equal to maxPrice' }],
        },
      },
    }))
    render(<App />)
    expect(await screen.findByText(/check your filters/i)).toBeInTheDocument()
    // Rows from a rejected query must not remain on screen.
    expect(screen.queryByText('123 Main St, Apt 4B')).not.toBeInTheDocument()
  })

  it('attaches a field-level issue to the input that caused it', async () => {
    mockApi(() => ({
      status: 400,
      body: {
        error: {
          code: 'INVALID_REQUEST',
          message: 'Invalid.',
          details: [{ field: 'pageSize', issue: 'Input should be greater than or equal to 1' }],
        },
      },
    }))
    render(<App />)
    expect(await screen.findByText('Input should be greater than or equal to 1')).toBeInTheDocument()
  })

  it('reports an unreachable API as a retryable failure', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch') }))
    render(<App />)
    expect(await screen.findByText(/search failed/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})

describe('filtering', () => {
  it('sends a typed keyword to the API', async () => {
    mockApi()
    render(<App />)
    await screen.findByText('123 Main St, Apt 4B')
    await userEvent.type(screen.getByLabelText(/keyword/i), 'garage')
    await waitFor(() => expect(lastQuery().get('keyword')).toBe('garage'))
  })

  it('omits a filter that the user cleared', async () => {
    mockApi()
    render(<App />)
    await screen.findByText('123 Main St, Apt 4B')
    const keyword = screen.getByLabelText(/keyword/i)
    await userEvent.type(keyword, 'pool')
    await waitFor(() => expect(lastQuery().get('keyword')).toBe('pool'))
    await userEvent.clear(keyword)
    await waitFor(() => expect(lastQuery().has('keyword')).toBe(false))
  })

  it('resets to page 1 when a filter changes', async () => {
    // The bug this guards: sitting on page 3, narrowing the filters, and
    // requesting page 3 of a result set that now has one page.
    mockApi()
    render(<App />)
    await screen.findByText('123 Main St, Apt 4B')

    await userEvent.click(screen.getAllByRole('button', { name: /go to page 3/i })[0])
    await waitFor(() => expect(lastQuery().get('page')).toBe('3'))

    await userEvent.type(screen.getByLabelText(/keyword/i), 'x')
    await waitFor(() => expect(lastQuery().get('page')).toBe('1'))
  })

  it('restores defaults when reset is clicked', async () => {
    mockApi()
    render(<App />)
    await screen.findByText('123 Main St, Apt 4B')
    await userEvent.type(screen.getByLabelText(/keyword/i), 'garage')
    await waitFor(() => expect(lastQuery().get('keyword')).toBe('garage'))

    await userEvent.click(screen.getByRole('button', { name: /^reset$/i }))
    await waitFor(() => expect(lastQuery().has('keyword')).toBe(false))
  })

  it('sends dedupe only when the box is ticked', async () => {
    mockApi()
    render(<App />)
    await screen.findByText('123 Main St, Apt 4B')
    expect(lastQuery().has('dedupe')).toBe(false)

    await userEvent.click(screen.getByRole('checkbox', { name: /merge duplicates/i }))
    await waitFor(() => expect(lastQuery().get('dedupe')).toBe('true'))
  })

  it('debounces typing into a single request', async () => {
    mockApi()
    render(<App />)
    await screen.findByText('123 Main St, Apt 4B')
    const before = searchUrls.length

    await userEvent.type(screen.getByLabelText(/keyword/i), 'kitchen')
    await waitFor(() => expect(lastQuery().get('keyword')).toBe('kitchen'))

    // Seven keystrokes must not mean seven round trips.
    expect(searchUrls.length - before).toBeLessThan(7)
  })
})

describe('pagination', () => {
  it('requests the page the user selects', async () => {
    mockApi()
    render(<App />)
    await screen.findByText('123 Main St, Apt 4B')
    await userEvent.click(screen.getAllByRole('button', { name: /go to page 2/i })[0])
    await waitFor(() => expect(lastQuery().get('page')).toBe('2'))
  })

  it('renders the rows returned for the requested page', async () => {
    mockApi((url) =>
      url.includes('page=2')
        ? { body: makeResponse({
            items: [makeListing({ key: 'MLS_A:A2', address: '456 Oak Ave' })],
            pageInfo: { page: 2, pageSize: 5, total: 12, totalPages: 3 },
          }) }
        : { body: makeResponse() },
    )
    render(<App />)
    await screen.findByText('123 Main St, Apt 4B')
    await userEvent.click(screen.getAllByRole('button', { name: /go to page 2/i })[0])
    expect(await screen.findByText('456 Oak Ave')).toBeInTheDocument()
    expect(screen.queryByText('123 Main St, Apt 4B')).not.toBeInTheDocument()
  })

  it('shows the result count from the server, not the visible row count', async () => {
    mockApi()
    render(<App />)
    const counts = await screen.findAllByText(/of 12 listings/)
    expect(counts.length).toBeGreaterThan(0)
  })
})

describe('result rows', () => {
  it('shows the relevance score for each row', async () => {
    mockApi()
    render(<App />)
    const row = (await screen.findByText('123 Main St, Apt 4B')).closest('tr')!
    expect(within(row).getByText('89.0')).toBeInTheDocument()
  })

  it('marks rows that merged duplicates from another feed', async () => {
    mockApi(() => ({
      body: makeResponse({ items: [makeListing({ mergedFrom: ['MLS_B:B7'] })] }),
    }))
    render(<App />)
    expect(await screen.findByText('+1 duplicate')).toBeInTheDocument()
  })
})

describe('the address bar', () => {
  const url = () => window.location.pathname + window.location.search

  it('leaves a clean URL alone until the user searches', async () => {
    mockApi()
    render(<App />)
    await screen.findByText('123 Main St, Apt 4B')
    expect(url()).toBe('/')
  })

  it('reflects a filter the user typed', async () => {
    mockApi()
    render(<App />)
    await screen.findByText('123 Main St, Apt 4B')
    await userEvent.type(screen.getByLabelText(/keyword/i), 'pool')
    await waitFor(() => expect(window.location.search).toContain('keyword=pool'))
  })

  it('reflects the current page', async () => {
    mockApi()
    render(<App />)
    await screen.findByText('123 Main St, Apt 4B')
    await userEvent.click(screen.getAllByRole('button', { name: /go to page 2/i })[0])
    await waitFor(() => expect(window.location.search).toContain('page=2'))
  })

  it('opens a shared link on the search it promised', async () => {
    // The bookmark / shared-link case: state comes from the URL, not defaults.
    window.history.replaceState(null, '', '/?city=Reston&minBedrooms=3&page=1&pageSize=5&sort=relevance')
    mockApi()
    render(<App />)
    await waitFor(() => expect(searchUrls.length).toBeGreaterThan(0))
    expect(lastQuery().get('city')).toBe('Reston')
    expect(lastQuery().get('minBedrooms')).toBe('3')
    expect(screen.getByLabelText(/keyword/i)).toHaveValue('')
    expect(await screen.findByDisplayValue('3')).toBeInTheDocument()
  })

  it('survives a reload, because the state lives in the URL', async () => {
    mockApi()
    const { unmount } = render(<App />)
    await screen.findByText('123 Main St, Apt 4B')
    await userEvent.type(screen.getByLabelText(/keyword/i), 'garage')
    await waitFor(() => expect(window.location.search).toContain('keyword=garage'))

    unmount()            // a reload: the component tree is rebuilt from scratch
    render(<App />)
    await waitFor(() => expect(lastQuery().get('keyword')).toBe('garage'))
  })
})

describe('history navigation', () => {
  it('does not add a history entry per keystroke', async () => {
    mockApi()
    render(<App />)
    await screen.findByText('123 Main St, Apt 4B')
    const before = window.history.length

    await userEvent.type(screen.getByLabelText(/keyword/i), 'kitchen')
    await waitFor(() => expect(window.location.search).toContain('keyword=kitchen'))

    // Seven characters must not cost seven presses of the back button.
    expect(window.history.length - before).toBeLessThan(7)
  })

  it('adds one history entry when the user changes page', async () => {
    mockApi()
    render(<App />)
    await screen.findByText('123 Main St, Apt 4B')
    const before = window.history.length

    await userEvent.click(screen.getAllByRole('button', { name: /go to page 2/i })[0])
    await waitFor(() => expect(window.location.search).toContain('page=2'))

    expect(window.history.length).toBe(before + 1)
  })

  it('restores the previous search when the browser goes back', async () => {
    mockApi()
    render(<App />)
    await screen.findByText('123 Main St, Apt 4B')

    await userEvent.click(screen.getAllByRole('button', { name: /go to page 3/i })[0])
    await waitFor(() => expect(lastQuery().get('page')).toBe('3'))

    // jsdom updates location on back() but does not fire popstate itself.
    window.history.back()
    await waitFor(() => expect(window.location.search).not.toContain('page=3'))
    window.dispatchEvent(new PopStateEvent('popstate'))

    await waitFor(() => expect(lastQuery().get('page')).toBe('1'))
  })
})

describe('caching', () => {
  it('renders a repeated search from cache without a spinner', async () => {
    mockApi()
    render(<App />)
    await screen.findByText('123 Main St, Apt 4B')

    await userEvent.click(screen.getAllByRole('button', { name: /go to page 2/i })[0])
    await waitFor(() => expect(lastQuery().get('page')).toBe('2'))

    await userEvent.click(screen.getAllByRole('button', { name: /go to page 1/i })[0])
    // Page 1 is cached, so results stay on screen rather than flashing a spinner.
    expect(screen.queryByLabelText('Loading results')).not.toBeInTheDocument()
    expect(screen.getByText('123 Main St, Apt 4B')).toBeInTheDocument()
  })

  it('still revalidates a cached search', async () => {
    // Stale-while-revalidate: the cache is for perceived speed, not a licence
    // to serve data that may have changed.
    mockApi()
    render(<App />)
    await screen.findByText('123 Main St, Apt 4B')
    const firstRound = searchUrls.length

    await userEvent.click(screen.getAllByRole('button', { name: /go to page 2/i })[0])
    await waitFor(() => expect(lastQuery().get('page')).toBe('2'))
    await userEvent.click(screen.getAllByRole('button', { name: /go to page 1/i })[0])
    await waitFor(() => expect(lastQuery().get('page')).toBe('1'))

    expect(searchUrls.length).toBeGreaterThan(firstRound)
  })

  it('shows updated data when a revalidation returns something different', async () => {
    let call = 0
    mockApi(() => {
      call += 1
      return call === 1
        ? { body: makeResponse() }
        : { body: makeResponse({ items: [makeListing({ address: '999 Changed Rd' })] }) }
    })
    render(<App />)
    await screen.findByText('123 Main St, Apt 4B')

    await userEvent.click(screen.getAllByRole('button', { name: /go to page 2/i })[0])
    expect(await screen.findByText('999 Changed Rd')).toBeInTheDocument()
  })

  it('does not cache a failed request, so retry really retries', async () => {
    let fail = true
    mockApi(() =>
      fail
        ? { status: 400, body: { error: { code: 'INVALID_REQUEST', message: 'Nope.', details: [] } } }
        : { body: makeResponse() },
    )
    render(<App />)
    await screen.findByText(/check your filters/i)

    fail = false
    await userEvent.type(screen.getByLabelText(/keyword/i), 'x')
    expect(await screen.findByText('123 Main St, Apt 4B')).toBeInTheDocument()
  })
})
