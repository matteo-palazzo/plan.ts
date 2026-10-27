import { useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import { tasks } from "../api/endpoints";
import type { CalendarRule, NotifyMode, Recurrence, Task, TaskInput, TaskType } from "../api/types";
import { Button, Dialog, Field, InlineError } from "../components/ui";
import { NOTIFY_MODES, TASK_TYPES, WEEKDAYS_SHORT, todayIso } from "../lib/format";

interface Props {
  plantId: number;
  task: Task | null;
  open: boolean;
  onClose: () => void;
  onSaved: (task: Task) => void;
}

type Errors = Partial<Record<"name" | "interval_days" | "calendar_rule" | "start_date" | "end_date", string>>;

function initialState(task: Task | null) {
  const rule = task?.calendar_rule;
  return {
    name: task?.name ?? "",
    taskType: (task?.task_type ?? "watering") as TaskType,
    description: task?.description ?? "",
    recurrence: (task?.recurrence ?? "interval") as Recurrence,
    intervalDays: String(task?.interval_days ?? 7),
    calendarKind: (rule?.kind ?? "weekly") as CalendarRule["kind"],
    weekdays: rule?.kind === "weekly" ? rule.weekdays : [0],
    monthDay: String(rule?.kind === "monthly" ? rule.day : 1),
    startDate: task?.start_date ?? todayIso(),
    endDate: task?.end_date ?? "",
    notify: (task?.notify ?? "day_of") as NotifyMode,
  };
}

export function TaskEditor({ plantId, task, open, onClose, onSaved }: Props) {
  const [state, setState] = useState(() => initialState(task));
  const [errors, setErrors] = useState<Errors>({});
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  function set<K extends keyof typeof state>(key: K, value: (typeof state)[K]) {
    setState((current) => ({ ...current, [key]: value }));
  }

  function validate(): TaskInput | null {
    const found: Errors = {};
    const name = state.name.trim() || (state.taskType !== "other" ? TASK_TYPES[state.taskType] : "");
    if (!name) found.name = "Il nome è obbligatorio";
    const interval = Number(state.intervalDays);
    if (state.recurrence === "interval" && (!Number.isInteger(interval) || interval < 1 || interval > 730)) {
      found.interval_days = "Indica un numero di giorni tra 1 e 730";
    }
    const day = Number(state.monthDay);
    if (state.recurrence === "calendar") {
      if (state.calendarKind === "weekly" && !state.weekdays.length) found.calendar_rule = "Scegli almeno un giorno";
      if (state.calendarKind === "monthly" && (!Number.isInteger(day) || day < 1 || day > 31)) {
        found.calendar_rule = "Il giorno deve essere tra 1 e 31";
      }
    }
    if (!state.startDate) found.start_date = "Indica la data";
    if (state.endDate && state.startDate && state.endDate < state.startDate) {
      found.end_date = "La data finale non può precedere quella iniziale";
    }
    setErrors(found);
    if (Object.keys(found).length) return null;
    return {
      name,
      task_type: state.taskType,
      description: state.description.trim() || null,
      recurrence: state.recurrence,
      interval_days: state.recurrence === "interval" ? interval : null,
      calendar_rule:
        state.recurrence === "calendar"
          ? state.calendarKind === "weekly"
            ? { kind: "weekly", weekdays: [...state.weekdays].sort() }
            : { kind: "monthly", day }
          : null,
      start_date: state.startDate,
      end_date: state.recurrence === "once" ? null : state.endDate || null,
      notify: state.notify,
    };
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const payload = validate();
    if (!payload) return;
    setBusy(true);
    setError(null);
    try {
      const saved = task ? await tasks.update(task.id, payload) : await tasks.create(plantId, payload);
      onSaved(saved);
    } catch (caught) {
      if (caught instanceof ApiError && caught.fieldErrors.length) {
        setErrors(Object.fromEntries(caught.fieldErrors.map((item) => [item.field, item.message])) as Errors);
      }
      setError(caught);
      setBusy(false);
    }
  }

  const startLabel = state.recurrence === "once" ? "Scadenza" : state.recurrence === "interval" ? "Prima scadenza" : "A partire dal";

  return (
    <Dialog open={open} title={task ? "Modifica task" : "Nuovo task"} onClose={onClose} wide>
      <form className="form" onSubmit={submit} noValidate>
        <div className="form-row">
          <Field label="Tipologia">
            {(id) => (
              <select id={id} value={state.taskType} onChange={(event) => set("taskType", event.target.value as TaskType)}>
                {Object.entries(TASK_TYPES).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label="Nome" error={errors.name} hint={state.name ? undefined : `Se vuoto: «${TASK_TYPES[state.taskType]}»`}>
            {(id, describedBy) => (
              <input
                id={id}
                aria-describedby={describedBy}
                maxLength={120}
                value={state.name}
                onChange={(event) => set("name", event.target.value)}
              />
            )}
          </Field>
        </div>

        <fieldset className="segmented">
          <legend>Ripetizione</legend>
          {(
            [
              ["once", "Una volta"],
              ["interval", "Ogni N giorni"],
              ["calendar", "A calendario"],
            ] as const
          ).map(([value, label]) => (
            <label key={value} className={state.recurrence === value ? "selected" : undefined}>
              <input
                type="radio"
                name="recurrence"
                value={value}
                checked={state.recurrence === value}
                onChange={() => set("recurrence", value)}
              />
              {label}
            </label>
          ))}
        </fieldset>

        {state.recurrence === "interval" ? (
          <Field
            label="Ogni quanti giorni"
            error={errors.interval_days}
            hint="La scadenza successiva si calcola dal giorno in cui segni il task come fatto."
          >
            {(id, describedBy) => (
              <input
                id={id}
                aria-describedby={describedBy}
                type="number"
                inputMode="numeric"
                min={1}
                max={730}
                value={state.intervalDays}
                onChange={(event) => set("intervalDays", event.target.value)}
              />
            )}
          </Field>
        ) : null}

        {state.recurrence === "calendar" ? (
          <div className="calendar-rule">
            <fieldset className="segmented segmented-small">
              <legend>Regola</legend>
              {(
                [
                  ["weekly", "Giorni della settimana"],
                  ["monthly", "Giorno del mese"],
                ] as const
              ).map(([value, label]) => (
                <label key={value} className={state.calendarKind === value ? "selected" : undefined}>
                  <input
                    type="radio"
                    name="calendar-kind"
                    checked={state.calendarKind === value}
                    onChange={() => set("calendarKind", value)}
                  />
                  {label}
                </label>
              ))}
            </fieldset>
            {state.calendarKind === "weekly" ? (
              <fieldset className="weekday-picker">
                <legend className="visually-hidden">Giorni della settimana</legend>
                {WEEKDAYS_SHORT.map((label, index) => (
                  <label key={label} className={state.weekdays.includes(index) ? "selected" : undefined}>
                    <input
                      type="checkbox"
                      checked={state.weekdays.includes(index)}
                      onChange={(event) =>
                        set(
                          "weekdays",
                          event.target.checked ? [...state.weekdays, index] : state.weekdays.filter((day) => day !== index),
                        )
                      }
                    />
                    {label}
                  </label>
                ))}
              </fieldset>
            ) : (
              <Field label="Giorno del mese" hint="Nei mesi più corti si usa l'ultimo giorno del mese (es. 31 → 30 aprile, 28 febbraio).">
                {(id, describedBy) => (
                  <input
                    id={id}
                    aria-describedby={describedBy}
                    type="number"
                    inputMode="numeric"
                    min={1}
                    max={31}
                    value={state.monthDay}
                    onChange={(event) => set("monthDay", event.target.value)}
                  />
                )}
              </Field>
            )}
            {errors.calendar_rule ? <p className="field-error">{errors.calendar_rule}</p> : null}
            <p className="field-hint">Le scadenze restano ancorate al calendario anche se completi il task in ritardo.</p>
          </div>
        ) : null}

        <div className="form-row">
          <Field label={startLabel} error={errors.start_date}>
            {(id) => (
              <input id={id} type="date" required value={state.startDate} onChange={(event) => set("startDate", event.target.value)} />
            )}
          </Field>
          {state.recurrence !== "once" ? (
            <Field label="Fino al (facoltativo)" error={errors.end_date}>
              {(id) => (
                <input id={id} type="date" value={state.endDate} min={state.startDate} onChange={(event) => set("endDate", event.target.value)} />
              )}
            </Field>
          ) : null}
        </div>

        <Field label="Promemoria Telegram">
          {(id) => (
            <select id={id} value={state.notify} onChange={(event) => set("notify", event.target.value as NotifyMode)}>
              {Object.entries(NOTIFY_MODES).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          )}
        </Field>

        <Field label="Note (facoltative)">
          {(id) => (
            <textarea id={id} rows={2} maxLength={5000} value={state.description} onChange={(event) => set("description", event.target.value)} />
          )}
        </Field>

        {task ? (
          <p className="field-hint">Le modifiche valgono per le scadenze future: lo storico già registrato non cambia.</p>
        ) : null}
        <InlineError error={error} />
        <div className="form-actions">
          <Button variant="ghost" onClick={onClose}>
            Annulla
          </Button>
          <Button type="submit" variant="primary" busy={busy}>
            {task ? "Salva modifiche" : "Crea task"}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
