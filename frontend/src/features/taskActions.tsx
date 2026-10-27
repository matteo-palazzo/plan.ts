import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { errorMessage } from "../api/client";
import { diary, occurrences } from "../api/endpoints";
import type { Occurrence } from "../api/types";
import { useToast } from "../components/toast";
import { Button, Dialog, Field, InlineError } from "../components/ui";
import { PhotoPicker } from "./photos";

interface TaskActions {
  complete: (occurrence: Occurrence) => Promise<boolean>;
  skip: (occurrence: Occurrence) => Promise<boolean>;
  busyId: number | null;
  onChange: (listener: () => void) => () => void;
  refresh: () => void;
}

const TaskActionsContext = createContext<TaskActions | null>(null);

interface FollowUp {
  entryId: number;
  taskName: string;
  plantName: string;
}

export function TaskActionsProvider({ children }: { children: ReactNode }) {
  const toast = useToast();
  const [busyId, setBusyId] = useState<number | null>(null);
  const [followUp, setFollowUp] = useState<FollowUp | null>(null);
  const [listeners] = useState(() => new Set<() => void>());

  const notify = useCallback(() => listeners.forEach((listener) => listener()), [listeners]);

  const onChange = useCallback(
    (listener: () => void) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    [listeners],
  );

  const complete = useCallback(
    async (occurrence: Occurrence) => {
      if (occurrence.id === null) return false;
      setBusyId(occurrence.id);
      try {
        const result = await occurrences.complete(occurrence.id);
        notify();
        toast(`Fatto: ${occurrence.task_name} · ${occurrence.plant_name}`, {
          tone: "success",
          actions: [
            {
              label: "Aggiungi nota o foto",
              onClick: () =>
                setFollowUp({
                  entryId: result.diary_entry_id,
                  taskName: occurrence.task_name,
                  plantName: occurrence.plant_name,
                }),
            },
          ],
        });
        return true;
      } catch (error) {
        toast(errorMessage(error), { tone: "error" });
        return false;
      } finally {
        setBusyId(null);
      }
    },
    [notify, toast],
  );

  const skip = useCallback(
    async (occurrence: Occurrence) => {
      if (occurrence.id === null) return false;
      const occurrenceId = occurrence.id;
      setBusyId(occurrenceId);
      try {
        await occurrences.skip(occurrenceId);
        notify();
        toast(`Saltato: ${occurrence.task_name} · ${occurrence.plant_name}`, {
          actions: [
            {
              label: "Annulla",
              onClick: () => {
                occurrences
                  .reopen(occurrenceId)
                  .then(notify)
                  .catch((error: unknown) => toast(errorMessage(error), { tone: "error" }));
              },
            },
          ],
        });
        return true;
      } catch (error) {
        toast(errorMessage(error), { tone: "error" });
        return false;
      } finally {
        setBusyId(null);
      }
    },
    [notify, toast],
  );

  const value = useMemo(
    () => ({ complete, skip, busyId, onChange, refresh: notify }),
    [complete, skip, busyId, onChange, notify],
  );

  return (
    <TaskActionsContext.Provider value={value}>
      {children}
      {followUp ? (
        <FollowUpDialog
          followUp={followUp}
          onClose={() => setFollowUp(null)}
          onSaved={() => {
            setFollowUp(null);
            notify();
            toast("Aggiunto al diario", { tone: "success" });
          }}
        />
      ) : null}
    </TaskActionsContext.Provider>
  );
}

function FollowUpDialog({ followUp, onClose, onSaved }: { followUp: FollowUp; onClose: () => void; onSaved: () => void }) {
  const [note, setNote] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      if (note.trim()) await diary.update(followUp.entryId, { body: note.trim(), category: null });
      if (files.length) await diary.addPhotos(followUp.entryId, files);
      onSaved();
    } catch (caught) {
      setError(caught);
      setBusy(false);
    }
  }

  return (
    <Dialog
      open
      title={`${followUp.taskName} · ${followUp.plantName}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Non ora
          </Button>
          <Button variant="primary" busy={busy} disabled={!note.trim() && !files.length} onClick={save}>
            Salva nel diario
          </Button>
        </>
      }
    >
      <p className="muted">Il completamento è già registrato. Puoi aggiungere una nota o delle foto, se vuoi.</p>
      <Field label="Nota">
        {(id) => <textarea id={id} rows={3} maxLength={5000} value={note} onChange={(event) => setNote(event.target.value)} />}
      </Field>
      <PhotoPicker files={files} onChange={setFiles} />
      <InlineError error={error} />
    </Dialog>
  );
}

export function useTaskActions(): TaskActions {
  const context = useContext(TaskActionsContext);
  if (!context) throw new Error("useTaskActions deve essere usato dentro TaskActionsProvider");
  return context;
}
