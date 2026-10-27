import { useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import { occurrences, tasks } from "../api/endpoints";
import type { Occurrence, Task } from "../api/types";
import { useToast } from "../components/toast";
import { Button, ConfirmDialog, Dialog, EmptyState, ErrorState, Field, InlineError, Loading, StatusBadge } from "../components/ui";
import {
  NOTIFY_MODES,
  TASK_TYPE_ICONS,
  addDays,
  describeRecurrence,
  formatDate,
  formatDateTime,
  todayIso,
} from "../lib/format";
import { useAsync } from "../lib/useAsync";
import { OccurrenceRow } from "./OccurrenceRow";
import { TaskEditor } from "./TaskEditor";
import { useTaskActions } from "./taskActions";

export function TasksPanel({ plantId, archived }: { plantId: number; archived: boolean }) {
  const { data, error, loading, reload } = useAsync(() => tasks.forPlant(plantId), [plantId]);
  const { onChange, refresh } = useTaskActions();
  const [editing, setEditing] = useState<Task | "new" | null>(null);
  const [detailsId, setDetailsId] = useState<number | null>(null);

  useEffect(() => onChange(() => void reload()), [onChange, reload]);

  const details = data?.find((task) => task.id === detailsId) ?? null;

  return (
    <section className="panel" aria-labelledby="tasks-title">
      <header className="panel-header">
        <h2 id="tasks-title">Task</h2>
        <Button size="sm" onClick={() => setEditing("new")}>
          + Nuovo task
        </Button>
      </header>
      {error ? <ErrorState error={error} onRetry={reload} /> : null}
      {!data && loading ? <Loading /> : null}
      {data && !data.length ? (
        <EmptyState title="Nessun task">Crea un task per ricordarti innaffiature, concimazioni, rinvasi e controlli.</EmptyState>
      ) : null}
      {data?.length ? (
        <ul className="task-list">
          {data.map((task) => (
            <li key={task.id} className={`task-card${task.status === "disabled" ? " task-disabled" : ""}`}>
              <button type="button" className="task-card-header" onClick={() => setDetailsId(task.id)}>
                <span aria-hidden="true">{TASK_TYPE_ICONS[task.task_type]}</span>
                <span className="task-card-title">
                  <strong>{task.name}</strong>
                  <span className="muted">
                    {describeRecurrence(task.recurrence, task.interval_days, task.calendar_rule)}
                    {task.is_suspended && task.suspended_until ? ` · sospeso fino al ${formatDate(task.suspended_until)}` : ""}
                    {task.status === "disabled" ? " · disattivato" : ""}
                  </span>
                </span>
                <span className="task-card-more" aria-hidden="true">
                  ⋯
                </span>
                <span className="visually-hidden">Dettagli e opzioni</span>
              </button>
              {task.pending.length && task.status === "active" && !task.is_suspended && !archived ? (
                <ul className="occurrence-list compact">
                  {task.pending.map((occurrence) => (
                    <OccurrenceRow key={occurrence.id} occurrence={occurrence} showPlant={false} />
                  ))}
                </ul>
              ) : null}
              {!task.pending.length && task.status === "active" ? <p className="muted task-done">Nessuna scadenza aperta.</p> : null}
            </li>
          ))}
        </ul>
      ) : null}

      {editing ? (
        <TaskEditor
          open
          plantId={plantId}
          task={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            refresh();
          }}
        />
      ) : null}
      {details ? (
        <TaskDetails
          task={details}
          onClose={() => setDetailsId(null)}
          onEdit={() => {
            setDetailsId(null);
            setEditing(details);
          }}
          onChanged={refresh}
        />
      ) : null}
    </section>
  );
}

interface DetailsProps {
  task: Task;
  onClose: () => void;
  onEdit: () => void;
  onChanged: () => void;
}

function TaskDetails({ task, onClose, onEdit, onChanged }: DetailsProps) {
  const toast = useToast();
  const history = useAsync(() => tasks.history(task.id), [task.id, task.updated_at]);
  const [suspendMode, setSuspendMode] = useState<"days" | "until">("days");
  const [days, setDays] = useState("7");
  const [until, setUntil] = useState(addDays(todayIso(), 14));
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [reopening, setReopening] = useState<Occurrence | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function run(key: string, action: () => Promise<unknown>, message?: string) {
    setBusy(key);
    setError(null);
    try {
      await action();
      onChanged();
      void history.reload();
      if (message) toast(message, { tone: "success" });
      return true;
    } catch (caught) {
      setError(caught);
      return false;
    } finally {
      setBusy(null);
    }
  }

  async function suspend() {
    const body = suspendMode === "days" ? { days: Number(days) } : { until };
    if (suspendMode === "days" && (!Number.isInteger(body.days) || Number(days) < 1)) {
      setError(new Error("Indica un numero di giorni valido"));
      return;
    }
    await run("suspend", () => tasks.suspend(task.id, body), "Task sospeso");
  }

  return (
    <Dialog open title={task.name} onClose={onClose} wide>
      <dl className="details">
        <div>
          <dt>Ripetizione</dt>
          <dd>{describeRecurrence(task.recurrence, task.interval_days, task.calendar_rule)}</dd>
        </div>
        <div>
          <dt>{task.recurrence === "once" ? "Scadenza" : "Dal"}</dt>
          <dd>
            {formatDate(task.start_date)}
            {task.end_date ? ` al ${formatDate(task.end_date)}` : ""}
          </dd>
        </div>
        <div>
          <dt>Promemoria</dt>
          <dd>{NOTIFY_MODES[task.notify]}</dd>
        </div>
        {task.description ? (
          <div>
            <dt>Note</dt>
            <dd className="pre-line">{task.description}</dd>
          </div>
        ) : null}
      </dl>

      <div className="button-row">
        <Button onClick={onEdit}>Modifica</Button>
        {task.status === "active" ? (
          <Button variant="ghost" busy={busy === "disable"} onClick={() => run("disable", () => tasks.setActive(task.id, false), "Task disattivato")}>
            Disattiva
          </Button>
        ) : (
          <Button busy={busy === "enable"} onClick={() => run("enable", () => tasks.setActive(task.id, true), "Task riattivato")}>
            Riattiva
          </Button>
        )}
        <Button variant="ghost" className="text-danger" onClick={() => setDeleting(true)}>
          Elimina
        </Button>
      </div>

      {task.status === "active" ? (
        <section className="subsection" aria-labelledby="suspend-title">
          <h3 id="suspend-title">Sospensione</h3>
          {task.is_suspended && task.suspended_until ? (
            <div className="button-row">
              <p>
                Sospeso fino al <strong>{formatDate(task.suspended_until)}</strong> (escluso).
              </p>
              <Button busy={busy === "resume"} onClick={() => run("resume", () => tasks.resume(task.id), "Task riattivato")}>
                Riattiva ora
              </Button>
            </div>
          ) : (
            <>
              <fieldset className="segmented segmented-small">
                <legend className="visually-hidden">Tipo di sospensione</legend>
                <label className={suspendMode === "days" ? "selected" : undefined}>
                  <input type="radio" checked={suspendMode === "days"} onChange={() => setSuspendMode("days")} />
                  Per una durata
                </label>
                <label className={suspendMode === "until" ? "selected" : undefined}>
                  <input type="radio" checked={suspendMode === "until"} onChange={() => setSuspendMode("until")} />
                  Fino a una data
                </label>
              </fieldset>
              <div className="form-row align-end">
                {suspendMode === "days" ? (
                  <Field label="Giorni">
                    {(id) => (
                      <input id={id} type="number" min={1} max={730} inputMode="numeric" value={days} onChange={(event) => setDays(event.target.value)} />
                    )}
                  </Field>
                ) : (
                  <Field label="Riattiva il">
                    {(id) => <input id={id} type="date" min={addDays(todayIso(), 1)} value={until} onChange={(event) => setUntil(event.target.value)} />}
                  </Field>
                )}
                <Button busy={busy === "suspend"} onClick={suspend}>
                  Sospendi
                </Button>
              </div>
              <p className="field-hint">
                Durante la sospensione il task non compare in dashboard e non invia promemoria. Le scadenze a calendario che cadono
                nel periodo vengono segnate come «sospese»; per i task a intervallo la scadenza slitta al giorno della riattivazione.
              </p>
            </>
          )}
        </section>
      ) : null}

      <InlineError error={error} />

      <section className="subsection" aria-labelledby="history-title">
        <h3 id="history-title">Storico</h3>
        {history.error ? <ErrorState error={history.error} onRetry={history.reload} /> : null}
        {!history.data && history.loading ? <Loading /> : null}
        {history.data && !history.data.length ? <p className="muted">Ancora nessuna esecuzione registrata.</p> : null}
        {history.data?.length ? (
          <ul className="history-list">
            {history.data.map((item) => (
              <li key={item.id}>
                <span>
                  <StatusBadge status={item.status} /> scadenza {formatDate(item.due_date)}
                  {item.completed_at ? <span className="muted"> · fatto il {formatDateTime(item.completed_at)}</span> : null}
                  {item.skipped_at ? <span className="muted"> · saltato il {formatDateTime(item.skipped_at)}</span> : null}
                </span>
                {item.status === "completed" || item.status === "skipped" ? (
                  <Button size="sm" variant="ghost" onClick={() => setReopening(item)}>
                    Annulla
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <ConfirmDialog
        open={reopening !== null}
        title={reopening?.status === "completed" ? "Annullare il completamento?" : "Annullare lo skip?"}
        message={
          <>
            <p>La scadenza del {reopening ? formatDate(reopening.due_date) : ""} tornerà da fare.</p>
            {reopening?.status === "completed" ? (
              <p>La voce del diario collegata, con eventuali note e foto, verrà eliminata.</p>
            ) : null}
            {task.recurrence === "interval" ? <p>La prossima scadenza verrà ricalcolata di conseguenza.</p> : null}
          </>
        }
        confirmLabel="Conferma annullamento"
        danger
        busy={busy === "reopen"}
        onCancel={() => setReopening(null)}
        onConfirm={async () => {
          if (!reopening?.id) return;
          const id = reopening.id;
          const ok = await run("reopen", () => occurrences.reopen(id), "Esecuzione annullata");
          if (ok) setReopening(null);
        }}
      />
      <ConfirmDialog
        open={deleting}
        title="Eliminare il task?"
        message={
          <>
            <p>Verranno eliminati la configurazione del task, le scadenze e lo storico delle esecuzioni.</p>
            <p>Le voci già presenti nel diario (con note e foto) restano. Se vuoi solo fermarlo, usa «Disattiva».</p>
          </>
        }
        confirmLabel="Elimina task"
        danger
        busy={busy === "delete"}
        onCancel={() => setDeleting(false)}
        onConfirm={async () => {
          setBusy("delete");
          try {
            await tasks.remove(task.id);
            toast("Task eliminato", { tone: "success" });
            onClose();
            onChanged();
          } catch (caught) {
            toast(errorMessage(caught), { tone: "error" });
          } finally {
            setBusy(null);
            setDeleting(false);
          }
        }}
      />
    </Dialog>
  );
}
