import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const component = readFileSync(new URL('../src/features/auth/HostedSignIn.tsx', import.meta.url), 'utf8')
const styles = readFileSync(new URL('../src/features/auth/hosted-sign-in.css', import.meta.url), 'utf8')
const shell = readFileSync(new URL('../src/app/App.tsx', import.meta.url), 'utf8')
const document = readFileSync(new URL('../index.html', import.meta.url), 'utf8')

test('Project Beacon owns the secure hosted sign-in language without changing the session exchange', () => {
  assert.match(component, /BTX Omni/)
  assert.match(component, /Project Beacon/)
  assert.match(component, /api\.signIn\(accessCode\)/)
  assert.match(component, /autoComplete="current-password"/)
  assert.match(component, /role="alert"/)
  assert.match(component, /Simulated data environment/)
  assert.doesNotMatch(component, /Hosted POC access|Omni Prospect/)
})

test('Project Beacon presentation is responsive, keyboard-visible and motion-safe', () => {
  assert.match(styles, /@media \(max-width: 900px\)/)
  assert.match(styles, /@media \(max-width: 480px\)/)
  assert.match(styles, /prefers-reduced-motion: reduce/)
  assert.match(styles, /:focus-within/)
  assert.match(styles, /--beacon-red: #d21f38/)
})

test('the authenticated shell and browser title use the Project Beacon product name', () => {
  assert.match(shell, /BTX Omni · Project Beacon/)
  assert.match(shell, /<small>Project Beacon<\/small>/)
  assert.match(document, /<title>BTX Omni — Project Beacon<\/title>/)
})
