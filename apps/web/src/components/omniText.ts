export function safeChatLink(url: string): string | undefined {
  return /^(https?:\/\/|#\/)/i.test(url) && !/[\s<>"']/.test(url) ? url : undefined
}

export const isPortfolioQuestion = (question: string) => /\b(?:which|what|list|show|compare|rank|summarize)\b.*\b(?:accounts|organizations|companies|portfolio)\b/i.test(question)

export async function readChatStream(body: ReadableStream<Uint8Array>, signal: AbortSignal, receive: (event: string, data: Record<string, unknown>) => void) {
  const reader = body.getReader(), decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      if (signal.aborted) throw new DOMException('Stopped', 'AbortError')
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let boundary: number
      while ((boundary = buffer.indexOf('\n\n')) >= 0) {
        const block = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2)
        const event = block.split('\n').find(line => line.startsWith('event: '))?.slice(7)
        const data = block.split('\n').filter(line => line.startsWith('data: ')).map(line => line.slice(6)).join('\n')
        if (event && data) receive(event, JSON.parse(data) as Record<string, unknown>)
      }
    }
  } finally { await reader.cancel(); reader.releaseLock() }
}
