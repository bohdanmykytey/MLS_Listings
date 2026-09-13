/**
 * Mirrors the backend contract in `backend/app/models.py`.
 *
 * Hand-maintained rather than generated: the API is small, and a generated
 * client would be more machinery than this exercise needs. If these drift, the
 * backend is the source of truth. (`GET /openapi.json` is the reference.)
 */

export type ListingStatus = 'active' | 'pending' | 'sold'

export type SortOption = 'relevance' | 'priceAsc' | 'priceDesc' | 'newest'

export interface ScoreBreakdown {
  budgetFit: number
  recency: number
  budgetWeight: number
  recencyWeight: number
}

export interface ScoredListing {
  /** Composite "SOURCE:ID" — `id` alone is not unique across feeds, so this
   *  is what React keys and dedupe references use. */
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

/** The form's state. Text inputs stay strings so a half-typed number is not
 *  coerced to NaN mid-keystroke; conversion happens once, in the client. */
export interface SearchFormState {
  minPrice: string
  maxPrice: string
  minBedrooms: string
  city: string
  keyword: string
  targetBudget: string
  dedupe: boolean
  sort: SortOption
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
