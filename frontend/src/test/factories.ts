/**
 * Test data builders.
 *
 * Components are rendered against objects shaped exactly like the API's, so a
 * contract change shows up as a type error here rather than as a runtime
 * surprise in the browser.
 */

import type { PageInfo, ScoredListing, SearchResponse } from '../api/types'

export function makeListing(overrides: Partial<ScoredListing> = {}): ScoredListing {
  return {
    key: 'MLS_A:A1',
    id: 'A1',
    source: 'MLS_A',
    address: '123 Main St, Apt 4B',
    city: 'Springfield',
    state: 'VA',
    zip: '22150',
    price: 450000,
    bedrooms: 2,
    bathrooms: 1.5,
    sqft: 980,
    latitude: 38.7893,
    longitude: -77.1873,
    listedDate: '2026-08-29',
    status: 'active',
    description: 'Bright top-floor condo near shops and transit.',
    relevanceScore: 88.95,
    scoreBreakdown: { budgetFit: 1, negotiability: 0.24, budgetWeight: 0.6, negotiabilityWeight: 0.4 },
    mergedFrom: [],
    ...overrides,
  }
}

export function makePageInfo(overrides: Partial<PageInfo> = {}): PageInfo {
  return { page: 1, pageSize: 5, total: 12, totalPages: 3, ...overrides }
}

export function makeResponse(overrides: Partial<SearchResponse> = {}): SearchResponse {
  return {
    items: [makeListing()],
    pageInfo: makePageInfo(),
    applied: {},
    ...overrides,
  }
}
