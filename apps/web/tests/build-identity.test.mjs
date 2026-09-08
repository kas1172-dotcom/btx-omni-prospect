import assert from 'node:assert/strict'
import test from 'node:test'
import { readBuildIdentity } from '../build/identity.mjs'

const sha = 'a'.repeat(40)
const tree = 'b'.repeat(40)
const git = (changes = {}) => args => ({ 'remote get-url origin': 'https://github.com/kas1172-dotcom/btx-omni-prospect.git',
  'rev-parse HEAD': sha, 'rev-parse HEAD^{tree}': tree, 'status --porcelain --untracked-files=normal': '', ...changes })[args.join(' ')] ?? null

test('build identity verifies repository and exact provider SHA without leaking environment', () => {
  const result = readBuildIdentity({ VERCEL_GIT_COMMIT_SHA: sha, GOOGLE_API_KEY: 'private-sentinel' }, git())
  assert.equal(result.commit_sha, sha)
  assert.equal(result.git_tree, tree)
  assert.equal(result.identity_state, 'CHECKED_CLEAN_CHECKOUT')
  assert.ok(!JSON.stringify(result).includes('private-sentinel'))
  assert.throws(() => readBuildIdentity({}, git({ 'remote get-url origin': 'https://github.com/kas1172-dotcom/btx-cro-monitor.git' })), /not the authorized/)
  assert.throws(() => readBuildIdentity({ VERCEL_GIT_COMMIT_SHA: 'c'.repeat(40) }, git()), /differ/)
  assert.throws(() => readBuildIdentity({ VERCEL_GIT_REPO_OWNER: 'wrong', VERCEL_GIT_REPO_SLUG: 'btx-omni-prospect' }, git()), /differs/)
})

test('dirty, missing and untrusted build identities never become clean proof', () => {
  assert.equal(readBuildIdentity({}, git({ 'status --porcelain --untracked-files=normal': ' M app.tsx' })).identity_state, 'UNVERIFIED_BUILD')
  const absent = readBuildIdentity({ VERCEL_GIT_COMMIT_SHA: sha }, () => null)
  assert.equal(absent.commit_sha, null)
  assert.equal(absent.worktree, 'unknown')
  const provider = readBuildIdentity({ VERCEL_GIT_COMMIT_SHA: sha, VERCEL_GIT_REPO_OWNER: 'kas1172-dotcom', VERCEL_GIT_REPO_SLUG: 'btx-omni-prospect' }, () => null)
  assert.equal(provider.commit_sha, sha)
  assert.equal(provider.identity_state, 'UNVERIFIED_BUILD')
  assert.equal(readBuildIdentity({ VERCEL_GIT_COMMIT_SHA: 'secret-invalid' }, () => null).commit_sha, null)
})
