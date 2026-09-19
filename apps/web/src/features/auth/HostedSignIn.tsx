import { useState } from 'react'
import { api } from '../../api/client'
import heroUrl from '../../assets/project-beacon-hero.jpg'
import './hosted-sign-in.css'

function BeaconBrand() {
  return <div className="beacon-brand" aria-label="BTX Precision">
    <span className="beacon-brand-mark" aria-hidden="true">BTX</span>
    <span className="beacon-brand-name">Precision</span>
  </div>
}

function BeaconStage({ children }: { children: React.ReactNode }) {
  return <main className="beacon-auth">
    <img className="beacon-auth-image" src={heroUrl} alt="" />
    <div className="beacon-auth-shade" aria-hidden="true" />
    <header className="beacon-auth-header">
      <BeaconBrand />
      <span className="beacon-environment"><i aria-hidden="true" />Simulated data environment</span>
    </header>
    <section className="beacon-story" aria-labelledby="beacon-title">
      <span className="beacon-kicker">BTX Omni</span>
      <h1 id="beacon-title">Project <strong>Beacon</strong></h1>
      <p className="beacon-statement">See the signal. Connect the evidence. Move with precision.</p>
      <p className="beacon-description">Commercial intelligence for the opportunities, risks, and relationships that deserve action.</p>
      <dl className="beacon-pillars" aria-label="Project Beacon workspace">
        <div><dt>Signal</dt><dd>Public and internal intelligence</dd></div>
        <div><dt>Context</dt><dd>Customers, programs and facilities</dd></div>
        <div><dt>Action</dt><dd>Evidence-backed next steps</dd></div>
      </dl>
    </section>
    <section className="beacon-access">{children}</section>
  </main>
}

export function HostedSessionCheck() {
  return <BeaconStage>
    <div className="beacon-check" role="status" aria-live="polite">
      <span className="beacon-check-indicator" aria-hidden="true" />
      <span className="beacon-form-kicker">Secure workspace</span>
      <h2>Opening Project Beacon</h2>
      <p>Confirming your protected workspace session.</p>
    </div>
  </BeaconStage>
}

export function HostedSignIn({ onAuthenticated }: { onAuthenticated: () => void }) {
  const [accessCode, setAccessCode] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [showCode, setShowCode] = useState(false)

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      await api.signIn(accessCode)
      setAccessCode('')
      onAuthenticated()
    } catch {
      setError('That access code could not be verified. Check the code or request a current one from your administrator.')
    } finally {
      setSubmitting(false)
    }
  }

  return <BeaconStage>
    <form className="beacon-sign-in" onSubmit={event => void submit(event)}>
      <div className="beacon-form-heading">
        <span className="beacon-form-kicker">Secure workspace</span>
        <h2>Sign in to Project Beacon</h2>
        <p>Use the access code issued by your BTX workspace administrator.</p>
      </div>
      <div className="beacon-code-field">
        <label htmlFor="beacon-access-code">Access code</label>
        <span className="beacon-code-control">
          <input
            id="beacon-access-code"
            type={showCode ? 'text' : 'password'}
            autoComplete="current-password"
            autoFocus
            value={accessCode}
            onChange={event => setAccessCode(event.target.value)}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? 'beacon-sign-in-error beacon-code-note' : 'beacon-code-note'}
            required
          />
          <button type="button" className="beacon-reveal" aria-pressed={showCode} onClick={() => setShowCode(value => !value)}>
            {showCode ? 'Hide' : 'Show'}
          </button>
        </span>
      </div>
      {error && <p className="beacon-error" id="beacon-sign-in-error" role="alert">{error}</p>}
      <button className="beacon-submit" type="submit" disabled={submitting || !accessCode.trim()}>
        <span>{submitting ? 'Verifying access…' : 'Enter Project Beacon'}</span>
        <span aria-hidden="true">&#8594;</span>
      </button>
      <p className="beacon-security" id="beacon-code-note"><span aria-hidden="true">&#9670;</span>Your code is exchanged securely with the server and is never stored in this browser.</p>
    </form>
  </BeaconStage>
}
