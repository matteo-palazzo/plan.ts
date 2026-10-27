import { useState, type FormEvent } from "react";
import { errorMessage } from "../api/client";
import { auth, groups, system, tags } from "../api/endpoints";
import type { Group, Tag } from "../api/types";
import { useAuth } from "../auth";
import { useToast } from "../components/toast";
import { Button, ConfirmDialog, ErrorState, Field, InlineError, Loading, TagChip } from "../components/ui";
import { formatBytes, formatDateTime } from "../lib/format";
import { useAsync } from "../lib/useAsync";

export function SettingsPage() {
  return (
    <div className="page settings-page">
      <header className="page-header">
        <h1>Impostazioni</h1>
      </header>
      <GroupsSection />
      <TagsSection />
      <TelegramSection />
      <BackupSection />
      <AccountSection />
    </div>
  );
}

interface NamedItem {
  id: number;
  name: string;
  plant_count: number;
}

interface ListEditorProps<T extends NamedItem> {
  title: string;
  description: string;
  items: T[] | undefined;
  loading: boolean;
  error: unknown;
  reload: () => Promise<void>;
  renderLabel: (item: T) => React.ReactNode;
  create: (name: string, color: string | null) => Promise<unknown>;
  rename: (item: T, name: string, color: string | null) => Promise<unknown>;
  remove: (item: T) => Promise<unknown>;
  deleteMessage: (item: T) => string;
  withColor?: boolean;
  colorOf?: (item: T) => string | null;
}

function ListEditor<T extends NamedItem>(props: ListEditorProps<T>) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [color, setColor] = useState("#2f855a");
  const [useColor, setUseColor] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editColor, setEditColor] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<unknown>, message: string) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await props.reload();
      toast(message, { tone: "success" });
      return true;
    } catch (caught) {
      setError(caught);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    if (await run(() => props.create(name.trim(), props.withColor && useColor ? color : null), "Creato")) setName("");
  }

  return (
    <section className="panel" aria-labelledby={`${props.title}-title`}>
      <h2 id={`${props.title}-title`}>{props.title}</h2>
      <p className="muted">{props.description}</p>
      {props.error ? <ErrorState error={props.error} onRetry={props.reload} /> : null}
      {!props.items && props.loading ? <Loading /> : null}
      {props.items?.length ? (
        <ul className="editable-list">
          {props.items.map((item) =>
            editingId === item.id ? (
              <li key={item.id}>
                <form
                  className="inline-form"
                  onSubmit={async (event) => {
                    event.preventDefault();
                    if (editName.trim() && (await run(() => props.rename(item, editName.trim(), editColor), "Salvato"))) setEditingId(null);
                  }}
                >
                  <input aria-label="Nome" value={editName} maxLength={100} onChange={(event) => setEditName(event.target.value)} autoFocus />
                  {props.withColor ? (
                    <input aria-label="Colore" type="color" value={editColor ?? "#888888"} onChange={(event) => setEditColor(event.target.value)} />
                  ) : null}
                  <Button size="sm" type="submit" variant="primary" busy={busy}>
                    Salva
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setEditingId(null)}>
                    Annulla
                  </Button>
                </form>
              </li>
            ) : (
              <li key={item.id}>
                <span>
                  {props.renderLabel(item)} <span className="muted small">· {item.plant_count} piante</span>
                </span>
                <span className="button-row">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      setEditingId(item.id);
                      setEditName(item.name);
                      setEditColor(props.colorOf?.(item) ?? null);
                    }}
                  >
                    Modifica
                  </Button>
                  <Button size="sm" variant="ghost" className="text-danger" onClick={() => setDeleting(item)}>
                    Elimina
                  </Button>
                </span>
              </li>
            ),
          )}
        </ul>
      ) : null}
      {props.items && !props.items.length ? <p className="muted">Nessun elemento.</p> : null}
      <form className="inline-form" onSubmit={submit}>
        <input aria-label={`Nuovo ${props.title.toLowerCase()}`} placeholder="Nome" maxLength={100} value={name} onChange={(event) => setName(event.target.value)} />
        {props.withColor ? (
          <label className="color-toggle">
            <input type="checkbox" checked={useColor} onChange={(event) => setUseColor(event.target.checked)} /> Colore
            {useColor ? <input aria-label="Colore" type="color" value={color} onChange={(event) => setColor(event.target.value)} /> : null}
          </label>
        ) : null}
        <Button type="submit" size="sm" disabled={!name.trim()} busy={busy}>
          Aggiungi
        </Button>
      </form>
      <InlineError error={error} />
      <ConfirmDialog
        open={deleting !== null}
        title={`Eliminare «${deleting?.name ?? ""}»?`}
        message={deleting ? props.deleteMessage(deleting) : ""}
        confirmLabel="Elimina"
        danger
        busy={busy}
        onCancel={() => setDeleting(null)}
        onConfirm={async () => {
          if (deleting && (await run(() => props.remove(deleting), "Eliminato"))) setDeleting(null);
        }}
      />
    </section>
  );
}

function GroupsSection() {
  const { data, loading, error, reload } = useAsync(() => groups.list(), []);
  return (
    <ListEditor<Group>
      title="Gruppi"
      description="Ogni pianta può appartenere a un solo gruppo, ad esempio una posizione come «Balcone sud»."
      items={data}
      loading={loading}
      error={error}
      reload={reload}
      renderLabel={(group) => <strong>{group.name}</strong>}
      create={(name) => groups.create(name, null)}
      rename={(group, name) => groups.update(group.id, name, group.description)}
      remove={(group) => groups.remove(group.id)}
      deleteMessage={(group) => `Le ${group.plant_count} piante del gruppo resteranno senza gruppo. Le piante non vengono eliminate.`}
    />
  );
}

function TagsSection() {
  const { data, loading, error, reload } = useAsync(() => tags.list(), []);
  return (
    <ListEditor<Tag>
      title="Tag"
      description="Etichette libere condivise tra le piante, ad esempio «Bonsai» o «Conifera»."
      items={data}
      loading={loading}
      error={error}
      reload={reload}
      withColor
      colorOf={(tag) => tag.color}
      renderLabel={(tag) => <TagChip name={tag.name} color={tag.color} />}
      create={(name, color) => tags.create({ name, color, description: null })}
      rename={(tag, name, color) => tags.update(tag.id, { name, color, description: tag.description })}
      remove={(tag) => tags.remove(tag.id)}
      deleteMessage={(tag) => `Il tag verrà tolto da ${tag.plant_count} piante. Le piante non vengono eliminate.`}
    />
  );
}

function TelegramSection() {
  const toast = useToast();
  const settings = useAsync(() => system.settings(), []);
  const [busy, setBusy] = useState(false);
  const telegram = settings.data?.telegram;

  async function test() {
    setBusy(true);
    try {
      await system.testTelegram();
      toast("Messaggio di prova inviato", { tone: "success" });
    } catch (caught) {
      toast(errorMessage(caught), { tone: "error" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="telegram-title">
      <h2 id="telegram-title">Notifiche Telegram</h2>
      {settings.error ? <ErrorState error={settings.error} onRetry={settings.reload} /> : null}
      {settings.data && telegram ? (
        <>
          <p>
            Stato:{" "}
            <strong>{telegram.configured ? "attive" : telegram.enabled ? "abilitate ma non configurate" : "disattivate"}</strong>
            {telegram.configured ? ` · invio dalle ${settings.data.notify_time} (${settings.data.timezone})` : ""}
          </p>
          <p className="muted small">
            Token e chat si configurano nel file <code>.env</code> del server (vedi la guida in <code>docs/telegram.md</code>). Ogni task
            sceglie se ricevere il promemoria il giorno prima, il giorno stesso, entrambi o nessuno.
          </p>
          <Button onClick={test} busy={busy} disabled={!telegram.configured}>
            Invia messaggio di prova
          </Button>
        </>
      ) : null}
      {settings.data ? (
        <dl className="details small">
          <div>
            <dt>Versione</dt>
            <dd>{settings.data.version}</dd>
          </div>
          <div>
            <dt>Foto</dt>
            <dd>
              max {settings.data.photo_max_mb} MB, {settings.data.photos_per_entry} per voce
            </dd>
          </div>
        </dl>
      ) : null}
    </section>
  );
}

function BackupSection() {
  const toast = useToast();
  const status = useAsync(() => system.backups(), []);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    try {
      status.setData(await system.runBackup());
      toast("Backup completato", { tone: "success" });
    } catch (caught) {
      toast(errorMessage(caught), { tone: "error" });
      void status.reload();
    } finally {
      setBusy(false);
    }
  }

  const data = status.data;
  return (
    <section className="panel" aria-labelledby="backup-title">
      <h2 id="backup-title">Backup</h2>
      {status.error ? <ErrorState error={status.error} onRetry={status.reload} /> : null}
      {!data && status.loading ? <Loading /> : null}
      {data ? (
        <>
          {data.last_result === "error" ? (
            <p className="banner banner-error" role="alert">
              Ultimo backup non riuscito ({data.last_run_at ? formatDateTime(data.last_run_at) : "data sconosciuta"}): {data.last_error}
            </p>
          ) : null}
          <p>
            Ultimo backup riuscito: <strong>{data.last_success_at ? formatDateTime(data.last_success_at) : "mai"}</strong>
          </p>
          <p className="muted small">
            Backup automatico settimanale, conservato per 30 giorni sul disco del Raspberry. Non protegge da guasti o furto del
            dispositivo: copia periodicamente i file su un altro supporto.
          </p>
          {data.backups.length ? (
            <ul className="editable-list small">
              {data.backups.map((item) => (
                <li key={item.name}>
                  <span>{formatDateTime(item.created_at)}</span>
                  <span className="muted">{formatBytes(item.size_bytes)}</span>
                </li>
              ))}
            </ul>
          ) : null}
          <Button onClick={run} busy={busy}>
            Esegui backup ora
          </Button>
        </>
      ) : null}
    </section>
  );
}

function AccountSection() {
  const { username, logout } = useAuth();
  const toast = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (next.length < 10) {
      setError(new Error("La nuova password deve avere almeno 10 caratteri"));
      return;
    }
    if (next !== repeat) {
      setError(new Error("Le due password non coincidono"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await auth.changePassword(current, next);
      setCurrent("");
      setNext("");
      setRepeat("");
      toast("Password aggiornata", { tone: "success" });
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="account-title">
      <h2 id="account-title">Account</h2>
      <div className="button-row">
        <p>
          Accesso come <strong>{username}</strong>
        </p>
        <Button onClick={() => void logout()}>Esci</Button>
      </div>
      <form className="form" onSubmit={submit}>
        <h3>Cambia password</h3>
        <input type="text" autoComplete="username" value={username ?? ""} readOnly hidden />
        <Field label="Password attuale">
          {(id) => <input id={id} type="password" autoComplete="current-password" value={current} onChange={(event) => setCurrent(event.target.value)} />}
        </Field>
        <div className="form-row">
          <Field label="Nuova password" hint="Almeno 10 caratteri">
            {(id, describedBy) => (
              <input id={id} aria-describedby={describedBy} type="password" autoComplete="new-password" value={next} onChange={(event) => setNext(event.target.value)} />
            )}
          </Field>
          <Field label="Ripeti la nuova password">
            {(id) => <input id={id} type="password" autoComplete="new-password" value={repeat} onChange={(event) => setRepeat(event.target.value)} />}
          </Field>
        </div>
        <InlineError error={error} />
        <div className="form-actions">
          <Button type="submit" busy={busy} disabled={!current || !next}>
            Aggiorna password
          </Button>
        </div>
      </form>
    </section>
  );
}
