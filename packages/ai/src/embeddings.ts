import { embed, embedMany } from 'ai'
import { google } from '@ai-sdk/google'

/**
 * The number of dimensions in the text-embedding-004 model output.
 */
export const EMBEDDING_DIMENSIONS = 768

/**
 * Sleep for a given number of milliseconds.
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * Retry an async function with exponential backoff.
 * @param fn - The async function to retry
 * @param maxAttempts - Maximum number of attempts (default: 3)
 * @param baseDelayMs - Base delay in milliseconds (default: 2000)
 */
async function withRetry<T>(
  fn: () => Promise<T>,
  maxAttempts: number = 3,
  baseDelayMs: number = 2000
): Promise<T> {
  let lastError: unknown
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn()
    } catch (error) {
      lastError = error
      if (attempt < maxAttempts) {
        const delay = baseDelayMs * Math.pow(2, attempt - 1) // 2s, 4s, 8s
        await sleep(delay)
      }
    }
  }
  throw lastError
}

/**
 * Returns a mock embedding vector of 768 zeros.
 * Used when GOOGLE_GENERATIVE_AI_API_KEY is not set.
 */
function mockEmbedding(): number[] {
  return new Array<number>(EMBEDDING_DIMENSIONS).fill(0)
}

/**
 * Embeds a single text string using Google text-embedding-004.
 * Returns a 768-dimensional vector.
 *
 * If GOOGLE_GENERATIVE_AI_API_KEY is not set, returns a mock vector of zeros.
 *
 * @param text - The text to embed
 * @returns A promise resolving to an array of 768 numbers
 */
export async function embedText(text: string): Promise<number[]> {
  if (!process.env['GOOGLE_GENERATIVE_AI_API_KEY']) {
    return mockEmbedding()
  }

  return withRetry(async () => {
    const { embedding } = await embed({
      model: google.textEmbeddingModel('text-embedding-004'),
      value: text,
    })
    return embedding
  })
}

/**
 * Embeds multiple text strings using Google text-embedding-004.
 * Returns an array of 768-dimensional vectors.
 *
 * If GOOGLE_GENERATIVE_AI_API_KEY is not set, returns mock vectors of zeros.
 *
 * @param texts - The texts to embed
 * @returns A promise resolving to an array of arrays of 768 numbers
 */
export async function embedBatch(texts: string[]): Promise<number[][]> {
  if (!process.env['GOOGLE_GENERATIVE_AI_API_KEY']) {
    return texts.map(() => mockEmbedding())
  }

  return withRetry(async () => {
    const { embeddings } = await embedMany({
      model: google.textEmbeddingModel('text-embedding-004'),
      values: texts,
    })
    return embeddings
  })
}

/**
 * Splits text into chunks of approximately maxTokens tokens with overlap.
 *
 * Uses 1 token ≈ 4 characters as an approximation.
 * Splits on paragraph boundaries (double newlines) when possible.
 *
 * @param text - The text to split
 * @param maxTokens - Maximum tokens per chunk (default: 2048)
 * @param overlapTokens - Number of overlap tokens between chunks (default: 200)
 * @returns An array of text chunks
 */
export function chunkText(
  text: string,
  maxTokens: number = 2048,
  overlapTokens: number = 200
): string[] {
  const approxCharsPerToken = 4
  const maxChars = maxTokens * approxCharsPerToken
  const overlapChars = overlapTokens * approxCharsPerToken

  if (text.length <= maxChars) return [text]

  const chunks: string[] = []
  // Split by paragraphs first
  const paragraphs = text.split(/\n\n+/)
  let current = ''

  for (const para of paragraphs) {
    if ((current + para).length > maxChars && current.length > 0) {
      chunks.push(current.trim())
      // Keep overlap from end of current chunk
      current = current.slice(-overlapChars) + '\n\n' + para
    } else {
      current = current ? current + '\n\n' + para : para
    }
  }

  if (current.trim()) chunks.push(current.trim())
  return chunks
}
