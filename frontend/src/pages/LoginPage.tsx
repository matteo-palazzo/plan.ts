import { useState, type FormEvent } from "react";
import { useAuth } from "../auth";
import { Button, Field, InlineError } from "../components/ui";

export function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username.trim(), password);
    } catch (caught) {
      setError(caught);
      setBusy(false);
    }
  }

  return (
    <main className="login-page">
      <form className="login-card" onSubmit={submit}>
        <img src="/favicon.svg" alt="" width="48" height="48" />
        <h1>Piante</h1>
        <Field label="Nome utente">
          {(id) => (
            <input
              id={id}
              autoComplete="username"
              autoCapitalize="none"
              required
              value={username}
              onChange={(event) => setUsername(event.target.value)}
            />
          )}
        </Field>
        <Field label="Password">
          {(id) => (
            <input
              id={id}
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          )}
        </Field>
        <InlineError error={error} />
        <Button type="submit" variant="primary" size="lg" busy={busy}>
          Accedi
        </Button>
      </form>
    </main>
  );
}
