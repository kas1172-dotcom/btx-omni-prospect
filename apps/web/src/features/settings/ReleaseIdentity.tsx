import { frontendBuild } from '../../app/build'
import { Disclosure } from '../../components/UI'
import type { BackendBuildIdentity } from '../../types/api'

export function ReleaseIdentity({ backend }: { backend?: BackendBuildIdentity }) {
  const comparable = Boolean(frontendBuild.commit_sha && backend?.commit_sha)
  const mismatch = comparable && (frontendBuild.commit_sha !== backend?.commit_sha || frontendBuild.repository !== backend?.repository
    || Boolean(frontendBuild.git_tree && backend?.git_tree && frontendBuild.git_tree !== backend.git_tree))
  const clean = frontendBuild.worktree === 'clean' && backend?.worktree === 'clean'
  return <Disclosure title="Frontend and backend build identity">
    <p role={mismatch ? 'alert' : undefined}>{mismatch ? 'Version mismatch: frontend and backend do not identify the same release. Do not approve this deployment.'
      : comparable && clean ? 'Commit declarations agree. Hosting, data and user-journey checks are still required.'
        : 'Release identity is not verified. A local or modified checkout is not a qualified deployment.'}</p>
    <dl className="action-meta release-identity">
      <div><dt>Repository</dt><dd>{frontendBuild.repository}</dd></div>
      <div><dt>Frontend commit</dt><dd>{frontendBuild.commit_sha ?? 'Not recorded'} ({frontendBuild.worktree})</dd></div>
      <div><dt>Backend commit</dt><dd>{backend?.commit_sha ?? 'Not recorded'} ({backend?.worktree ?? 'unknown'})</dd></div>
      <div><dt>Frontend build time</dt><dd>{new Date(frontendBuild.built_at).toLocaleString()}</dd></div>
      <div><dt>Required database revision</dt><dd>{backend?.required_schema_revision ?? 'Not recorded'}</dd></div>
    </dl>
    <p className="muted">Public metadata only. Build declarations do not prove live Maps, Gemini, scheduler execution or a successful release.</p>
  </Disclosure>
}
