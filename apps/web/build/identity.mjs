import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const repository = 'kas1172-dotcom/btx-omni-prospect'
const cwd = fileURLToPath(new URL('../../..', import.meta.url))
const gitRead = args => {
  try { return execFileSync('git', args, { cwd, timeout: 3000, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim() }
  catch { return null }
}
const validSha = value => typeof value === 'string' && /^[0-9a-f]{40}$/.test(value) ? value : null

export function readBuildIdentity(env = process.env, git = gitRead) {
  const origin = git(['remote', 'get-url', 'origin'])
  if (origin && !['https://github.com/' + repository, 'https://github.com/' + repository + '.git', 'git@github.com:' + repository + '.git'].includes(origin)) {
    throw new Error('Build refused: this checkout is not the authorized Omni Prospect repository.')
  }
  const head = validSha(git(['rev-parse', 'HEAD']))
  const declared = validSha(env.VERCEL_GIT_COMMIT_SHA || env.BTX_RELEASE_SHA)
  if (head && declared && head !== declared) throw new Error('Build refused: provider and checkout commit identities differ.')
  const providerRepo = env.VERCEL_GIT_REPO_OWNER && env.VERCEL_GIT_REPO_SLUG ? `${env.VERCEL_GIT_REPO_OWNER}/${env.VERCEL_GIT_REPO_SLUG}` : null
  if (providerRepo && providerRepo !== repository) throw new Error('Build refused: provider repository identity differs.')
  const status = origin && head ? git(['status', '--porcelain', '--untracked-files=normal']) : null
  const worktree = status === null ? 'unknown' : status ? 'dirty' : 'clean'
  return { repository, commit_sha: head || (providerRepo === repository ? declared : null),
    git_tree: origin && head ? validSha(git(['rev-parse', 'HEAD^{tree}'])) : null,
    worktree, identity_state: origin && head && worktree === 'clean' ? 'CHECKED_CLEAN_CHECKOUT' : 'UNVERIFIED_BUILD',
    built_at: new Date().toISOString() }
}
