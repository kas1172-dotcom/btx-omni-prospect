import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'

const source = readFileSync(new URL('../src/components/omniText.ts', import.meta.url), 'utf8')
const compiled = ts.transpile(source, { target: ts.ScriptTarget.ES2023, module: ts.ModuleKind.ES2022 })
const { readChatStream, safeChatLink } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)

test('stream parser preserves split SSE events and unicode', async () => {
  const text = 'event: progress\ndata: {"text":"Checking…"}\n\nevent: answer\ndata: {"response":{"content":"Hello"}}\n\n'
  const bytes = new TextEncoder().encode(text), events = []
  const stream = new ReadableStream({ start(controller) { for (const byte of bytes) controller.enqueue(Uint8Array.of(byte)); controller.close() } })
  await readChatStream(stream, new AbortController().signal, (event, data) => events.push([event, data]))
  assert.equal(events[0][1].text, 'Checking…')
  assert.equal(events[1][1].response.content, 'Hello')
})

test('cancel stops stream consumption', async () => {
  const controller = new AbortController(); controller.abort()
  await assert.rejects(readChatStream(new ReadableStream({ start(c) { c.close() } }), controller.signal, () => assert.fail()), { name: 'AbortError' })
})

test('markdown links cannot execute scripts or raw HTML', () => {
  for (const link of ['javascript:alert(1)', 'data:text/html,a', '//evil.org', 'https://example.org/"onclick=x', '<script>']) assert.equal(safeChatLink(link), undefined)
  assert.equal(safeChatLink('https://example.org/news'), 'https://example.org/news')
  const component = readFileSync(new URL('../src/components/OmniMarkdown.tsx', import.meta.url), 'utf8')
  assert.doesNotMatch(component, /dangerouslySetInnerHTML/)
  assert.match(component, /safeChatLink/)
})

test('history has resume rename delete and actor-authenticated client calls', () => {
  const drawer = readFileSync(new URL('../src/components/OmniDrawer.tsx', import.meta.url), 'utf8')
  for (const method of ['chatHistory', 'chatResume', 'chatRename', 'chatDelete', 'chatFeedback', 'chatStream']) assert.ok(drawer.includes(method))
  assert.match(drawer, /controller.current\?\.abort/)
  assert.match(drawer, /Disclosure title="Sources"/)
  assert.match(drawer, /Disclosure title="Details"/)
})
