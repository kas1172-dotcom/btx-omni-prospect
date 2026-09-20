import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const accounts = readFileSync(new URL('../src/features/accounts/Accounts.tsx', import.meta.url), 'utf8')
const client = readFileSync(new URL('../src/api/client.ts', import.meta.url), 'utf8')

test('legacy relationship loading is abortable, times out, and offers retry', () => {
  assert.match(client, /relationships: \(accountId: string, signal\?: AbortSignal\)/)
  assert.match(accounts, /new AbortController\(\)/)
  assert.match(accounts, /20_000/)
  assert.match(accounts, /api\.relationships\(accountId, controller\.signal\)/)
  assert.match(accounts, /Relationship records unavailable/)
  assert.match(accounts, /setError\(''\); setRetry\(value => value \+ 1\)/)
})
