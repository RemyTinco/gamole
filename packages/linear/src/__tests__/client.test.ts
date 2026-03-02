import { describe, it, expect } from 'bun:test'

// Test the rate-limit detection logic that lives in LinearClient.
// The isRateLimited helper is private, so we replicate the same logic here
// to ensure the detection criteria remain correct (G16: code=RATELIMITED).

describe('Linear rate limit detection', () => {
  it('detects RATELIMITED error code in response.errors', () => {
    const error = {
      response: {
        errors: [{ extensions: { code: 'RATELIMITED' } }],
      },
    }
    const errors = (error as any)?.response?.errors ?? []
    const isRateLimited = Array.isArray(errors) &&
      errors.some((e: any) => e?.extensions?.code === 'RATELIMITED')
    expect(isRateLimited).toBe(true)
  })

  it('detects RATELIMITED error code directly on errors array', () => {
    const errors = [{ extensions: { code: 'RATELIMITED' } }]
    const isRateLimited = errors.some(
      (e: any) => e?.extensions?.code === 'RATELIMITED'
    )
    expect(isRateLimited).toBe(true)
  })

  it('does not flag non-rate-limit errors', () => {
    const errors = [{ extensions: { code: 'FORBIDDEN' } }]
    const isRateLimited = errors.some(
      (e: any) => e?.extensions?.code === 'RATELIMITED'
    )
    expect(isRateLimited).toBe(false)
  })

  it('does not flag errors with no extensions', () => {
    const errors = [{ message: 'Something went wrong' }]
    const isRateLimited = errors.some(
      (e: any) => e?.extensions?.code === 'RATELIMITED'
    )
    expect(isRateLimited).toBe(false)
  })

  it('does not flag empty errors array', () => {
    const errors: unknown[] = []
    const isRateLimited = errors.some(
      (e: any) => e?.extensions?.code === 'RATELIMITED'
    )
    expect(isRateLimited).toBe(false)
  })

  it('detects rate limit among multiple errors', () => {
    const errors = [
      { extensions: { code: 'VALIDATION_ERROR' } },
      { extensions: { code: 'RATELIMITED' } },
      { extensions: { code: 'INTERNAL_ERROR' } },
    ]
    const isRateLimited = errors.some(
      (e: any) => e?.extensions?.code === 'RATELIMITED'
    )
    expect(isRateLimited).toBe(true)
  })
})
