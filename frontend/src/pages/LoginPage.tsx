import { ArrowRight, LockKeyhole, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Button, Field, SubmitForm } from "../components/ui";

export function LoginPage() {
  const { user, login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (user)
    return (
      <Navigate
        to={user.role === "employee" ? "/chat" : "/dashboard"}
        replace
      />
    );
  async function submit() {
    setError("");
    setBusy(true);
    try {
      await login(email, password);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sign in failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login-page">
      <section className="login-story">
        <img src="/assets/branding/lockup-light.svg" alt="SOP Forge" />
        <div>
          <p className="eyebrow">Governed decisions, clearly made</p>
          <h1>Turn policy into confident action.</h1>
          <p>
            One secure workspace for employee requests, accountable reviews, and
            a complete decision trail.
          </p>
        </div>
        <ul>
          <li>
            <ShieldCheck />
            Policy grounded guidance
          </li>
          <li>
            <LockKeyhole />
            Role protected workflows
          </li>
        </ul>
      </section>
      <section className="login-panel">
        <SubmitForm onSubmit={submit} className="login-card">
          <div className="brand-mobile">
            <img src="/assets/branding/lockup.svg" alt="SOP Forge" />
          </div>
          <p className="eyebrow">Welcome back</p>
          <h2>Sign in to your workspace</h2>
          <p className="muted">
            Use your organization credentials to continue.
          </p>
          <Field label="Work email">
            <input
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="name@company.com"
            />
          </Field>
          <Field label="Password">
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={4}
            />
          </Field>
          {error && (
            <div className="inline-error" role="alert">
              {error}
            </div>
          )}
          <Button type="submit" disabled={busy}>
            {busy ? (
              "Signing in…"
            ) : (
              <>
                Sign in <ArrowRight size={17} />
              </>
            )}
          </Button>
          <p className="privacy-note">
            Protected by your organization’s access controls.
          </p>
        </SubmitForm>
      </section>
    </main>
  );
}
