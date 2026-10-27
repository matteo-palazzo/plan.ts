import { useCallback, useEffect, useState, type FormEvent } from "react";
import { diary, occurrences } from "../api/endpoints";
import type { DiaryCategory, DiaryEntry, Measurement, Photo } from "../api/types";
import { useToast } from "../components/toast";
import { Button, ConfirmDialog, Dialog, EmptyState, ErrorState, Field, InlineError, Loading } from "../components/ui";
import {
  DIARY_CATEGORIES,
  MEASUREMENT_KINDS,
  formatDateTime,
  formatLongDate,
  formatMm,
  fromLocalInput,
  toLocalInput,
} from "../lib/format";
import { PhotoGallery, PhotoPicker } from "./photos";

const PAGE_SIZE = 20;

interface Props {
  plantId: number;
  version: number;
  onChanged: () => void;
  onOpenMeasurement: (measurement: Measurement) => void;
}

export function DiaryTimeline({ plantId, version, onChanged, onOpenMeasurement }: Props) {
  const [items, setItems] = useState<DiaryEntry[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [editing, setEditing] = useState<DiaryEntry | "new" | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await diary.list(plantId, 0, PAGE_SIZE);
      setItems(page.items);
      setHasMore(page.has_more);
    } catch (caught) {
      setError(caught);
    } finally {
      setLoading(false);
    }
  }, [plantId, version]);

  useEffect(() => {
    void load();
  }, [load]);

  async function loadMore() {
    setLoadingMore(true);
    try {
      const page = await diary.list(plantId, items.length, PAGE_SIZE);
      setItems((current) => [...current, ...page.items]);
      setHasMore(page.has_more);
    } catch (caught) {
      setError(caught);
    } finally {
      setLoadingMore(false);
    }
  }

  async function deletePhoto(photo: Photo) {
    await diary.removePhoto(photo.id);
    onChanged();
  }

  return (
    <section className="panel" aria-labelledby="diary-title">
      <header className="panel-header">
        <h2 id="diary-title">Diario</h2>
        <Button size="sm" variant="primary" onClick={() => setEditing("new")}>
          + Aggiornamento
        </Button>
      </header>
      {error ? <ErrorState error={error} onRetry={load} /> : null}
      {loading && !items.length ? <Loading /> : null}
      {!loading && !error && !items.length ? (
        <EmptyState title="Il diario è vuoto">
          Aggiungi un aggiornamento con testo e foto. Anche i task completati e le misurazioni compariranno qui.
        </EmptyState>
      ) : null}
      <ol className="timeline">
        {items.map((entry) => (
          <li key={entry.id} className={`timeline-entry entry-${entry.kind}`}>
            <EntryView
              entry={entry}
              onEdit={() => setEditing(entry)}
              onOpenMeasurement={onOpenMeasurement}
              onDeletePhoto={entry.kind === "manual" && !entry.body && entry.photos.length === 1 ? undefined : deletePhoto}
            />
          </li>
        ))}
      </ol>
      {hasMore ? (
        <div className="center">
          <Button busy={loadingMore} onClick={loadMore}>
            Mostra voci precedenti
          </Button>
        </div>
      ) : null}
      {editing ? (
        <EntryDialog
          plantId={plantId}
          entry={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            onChanged();
          }}
        />
      ) : null}
    </section>
  );
}

interface EntryViewProps {
  entry: DiaryEntry;
  onEdit: () => void;
  onOpenMeasurement: (measurement: Measurement) => void;
  onDeletePhoto?: (photo: Photo) => Promise<void>;
}

function EntryView({ entry, onEdit, onOpenMeasurement, onDeletePhoto }: EntryViewProps) {
  if (entry.kind === "measurement" && entry.measurement) {
    const measurement = entry.measurement;
    return (
      <button type="button" className="entry-measurement" onClick={() => onOpenMeasurement(measurement)}>
        <span className="entry-marker" aria-hidden="true">
          📏
        </span>
        <span>
          <span className="entry-meta">
            <time dateTime={measurement.measured_on}>{formatLongDate(measurement.measured_on)}</time>
            <span className="badge badge-auto">Misurazione</span>
          </span>
          <span className="entry-title">
            {MEASUREMENT_KINDS[measurement.kind]}: <strong>{formatMm(measurement.value_mm)}</strong>
          </span>
        </span>
      </button>
    );
  }

  const isCompletion = entry.kind === "task_completion";
  return (
    <article>
      <header className="entry-header">
        <span className="entry-marker" aria-hidden="true">
          {isCompletion ? "✓" : "✎"}
        </span>
        <div className="entry-meta">
          <time dateTime={entry.occurred_at}>{formatDateTime(entry.occurred_at)}</time>
          {isCompletion ? <span className="badge badge-auto">Task completato</span> : null}
          {entry.category ? <span className="chip">{DIARY_CATEGORIES[entry.category]}</span> : null}
        </div>
        <Button size="sm" variant="ghost" onClick={onEdit} aria-label="Modifica voce">
          Modifica
        </Button>
      </header>
      {isCompletion ? <p className="entry-title">{entry.title}</p> : null}
      {entry.body ? <p className="entry-body pre-line">{entry.body}</p> : null}
      <PhotoGallery photos={entry.photos} onDelete={onDeletePhoto} />
    </article>
  );
}

interface EntryDialogProps {
  plantId: number;
  entry: DiaryEntry | null;
  onClose: () => void;
  onSaved: () => void;
}

function EntryDialog({ plantId, entry, onClose, onSaved }: EntryDialogProps) {
  const toast = useToast();
  const isCompletion = entry?.kind === "task_completion";
  const [body, setBody] = useState(entry?.body ?? "");
  const [category, setCategory] = useState<DiaryCategory | "">(entry?.category ?? "");
  const [when, setWhen] = useState(toLocalInput(entry ? new Date(entry.occurred_at) : new Date()));
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [confirm, setConfirm] = useState<"delete" | "reopen" | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!entry && !body.trim() && !files.length) {
      setError(new Error("Scrivi un testo o aggiungi almeno una foto"));
      return;
    }
    if (!when) {
      setError(new Error("Indica data e ora"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (!entry) {
        await diary.create(plantId, { body, category, occurred_at: fromLocalInput(when), files });
      } else {
        await diary.update(entry.id, {
          body: body.trim() || null,
          category: isCompletion ? null : category || null,
          occurred_at: isCompletion ? undefined : fromLocalInput(when),
        });
        if (files.length) await diary.addPhotos(entry.id, files);
      }
      onSaved();
    } catch (caught) {
      setError(caught);
      setBusy(false);
    }
  }

  async function runConfirmed() {
    if (!entry) return;
    setBusy(true);
    try {
      if (confirm === "delete") await diary.remove(entry.id);
      if (confirm === "reopen" && entry.occurrence_id) await occurrences.reopen(entry.occurrence_id);
      toast(confirm === "delete" ? "Voce eliminata" : "Completamento annullato", { tone: "success" });
      onSaved();
    } catch (caught) {
      setError(caught);
      setBusy(false);
      setConfirm(null);
    }
  }

  const title = !entry ? "Nuovo aggiornamento" : isCompletion ? `Completamento: ${entry.title ?? ""}` : "Modifica aggiornamento";

  return (
    <Dialog open title={title} onClose={onClose} wide>
      <form className="form" onSubmit={submit} noValidate>
        <Field label={isCompletion ? "Nota" : "Testo"}>
          {(id) => <textarea id={id} rows={4} maxLength={5000} value={body} onChange={(event) => setBody(event.target.value)} />}
        </Field>
        {!isCompletion ? (
          <div className="form-row">
            <Field label="Categoria (facoltativa)">
              {(id) => (
                <select id={id} value={category} onChange={(event) => setCategory(event.target.value as DiaryCategory | "")}>
                  <option value="">Nessuna</option>
                  {Object.entries(DIARY_CATEGORIES).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Field label="Data e ora">
              {(id) => (
                <input
                  id={id}
                  type="datetime-local"
                  max={toLocalInput(new Date())}
                  value={when}
                  onChange={(event) => setWhen(event.target.value)}
                />
              )}
            </Field>
          </div>
        ) : null}
        <PhotoPicker files={files} onChange={setFiles} existing={entry?.photos.length ?? 0} />
        {entry?.photos.length ? <p className="field-hint">Per eliminare una foto già caricata aprila a schermo intero.</p> : null}
        <InlineError error={error} />
        <div className="form-actions">
          {entry && !isCompletion ? (
            <Button variant="ghost" className="text-danger push-left" onClick={() => setConfirm("delete")}>
              Elimina voce
            </Button>
          ) : null}
          {entry && isCompletion && entry.occurrence_id ? (
            <Button variant="ghost" className="text-danger push-left" onClick={() => setConfirm("reopen")}>
              Annulla completamento
            </Button>
          ) : null}
          <Button variant="ghost" onClick={onClose}>
            Chiudi
          </Button>
          <Button type="submit" variant="primary" busy={busy}>
            Salva
          </Button>
        </div>
      </form>
      <ConfirmDialog
        open={confirm !== null}
        title={confirm === "delete" ? "Eliminare la voce?" : "Annullare il completamento?"}
        message={
          confirm === "delete" ? (
            "La voce e le sue foto verranno eliminate definitivamente."
          ) : (
            <>
              <p>Il task tornerà da fare per quella scadenza e questa voce del diario, con note e foto, verrà eliminata.</p>
              <p>Per i task a intervallo la prossima scadenza verrà ricalcolata.</p>
            </>
          )
        }
        confirmLabel={confirm === "delete" ? "Elimina" : "Annulla completamento"}
        danger
        busy={busy}
        onConfirm={runConfirmed}
        onCancel={() => setConfirm(null)}
      />
    </Dialog>
  );
}
