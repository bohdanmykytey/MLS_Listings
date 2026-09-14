/**
 * Mirrors `backend/app/models.py` by hand — the API is small enough that a
 * generated client isn't worth it. Backend is the source of truth if they drift.
 */

export type ListingStatus = 'active' | 'pending' | 'sold'

export interface ScoreBreakdown {
  budgetFit: number
  /** Buyer leverage from time on market: 0 when fresh, 1 once capped. */
  negotiability: number
  budgetWeight: number
  negotiabilityWeight: number
}

export interface ScoredListing {
  /** Composite "SOURCE:ID" — `id` alone isn't unique across feeds. */
  key: string
  id: string
  source: string
  address: string
  city: string
  state: string
  zip: string
  price: number
  bedrooms: number
  bathrooms: number
  sqft: number
  latitude: number
  longitude: number
  listedDate: string
  status: ListingStatus
  description: string
  relevanceScore: number
  scoreBreakdown: ScoreBreakdown
  /** Keys this row absorbed when dedupe is enabled; empty otherwise. */
  mergedFrom: string[]
}

export interface PageInfo {
  page: number
  pageSize: number
  total: number
  totalPages: number
}

export interface SearchResponse {
  items: ScoredListing[]
  pageInfo: PageInfo
  /** What the server actually applied, echoed back for transparency. */
  applied: Record<string, unknown>
}

/** Text inputs stay strings so a half-typed number isn't coerced to NaN. */
export interface SearchFormState {
  minPrice: string
  maxPrice: string
  minBedrooms: string
  city: string
  keyword: string
  targetBudget: string
  dedupe: boolean
  pageSize: string
}

export interface ErrorDetail {
  field: string | null
  issue: string
}

export interface ErrorBody {
  code: string
  message: string
  details: ErrorDetail[]
}
