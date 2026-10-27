import { lazy, Suspense, useState, type FormEvent } from "react";
import { measurements } from "../api/endpoints";
import type { ChartRange, LengthUnit, Measurement, MeasurementKind } from "../api/types";
import { Button, ConfirmDialog, Dialog, EmptyState, ErrorState, Field, InlineError, Loading } from "../components/ui";
import { MEASUREMENT_KINDS, UNITS, formatDate, formatMm, todayIso } from "../lib/format";
import { useAsync } from "../lib/useAsync";

const RANGES: Record<ChartRange, string> = { month: "Ultimo mese", year: "Ultimo anno", all: "Tutto" };
const KINDS = Object.keys(MEASUREMENT_KINDS) as MeasurementKind[];
const MeasurementChart = lazy(() => import("./MeasurementChart"));

interface Props {
  plantId: number;
  version: number;
  onChanged: () => void;
}

export function MeasurementsPanel({ plantId, version, onChanged }: Props) {
  const [range, setRange] = useState<ChartRange>("year");
  const charts = useAsync(() => measurements.charts(plantId, range), [plantId, range, version]);
  const list = useAsync(() => measurements.list(plantId), [plantId, version]);
  const [editing, setEditing] = useState<Measurement | "new" | null>(null);

  const total = list.data?.length ?? 0;

  return (
    <section className="panel" aria-labelledby="measurements-title">
      <header className="panel-header">
        <h2 id="measurements-title">Misurazioni</h2>
        <Button size="sm" onClick={() => setEditing("new")}>
          + Misurazione
        </Button>
      </header>
      {charts.error ? <ErrorState error={charts.error} onRetry={charts.reload} /> : null}
      {!charts.data && charts.loading ? <Loading /> : null}
      {list.data && total === 0 ? (
        <EmptyState title="Nessuna misurazione">
          Registra altezza, larghezza o diametro del tronco per seguire la crescita nel tempo.
        </EmptyState>
      ) : null}
      {charts.data && total > 0 ? (
        <>
          <div className="segmented segmented-small" role="group" aria-label="Intervallo dei grafici">
            {(Object.keys(RANGES) as ChartRange[]).map((key) => (
              <button
                key={key}
                type="button"
                className={range === key ? "selected" : undefined}
                aria-pressed={range === key}
                onClick={() => setRange(key)}
              >
                {RANGES[key]}
              </button>
            ))}
          </div>
          <Suspense fallback={<Loading label="Caricamento grafici…" />}>
            <div className="charts">
              {KINDS.map((kind) => (
                <MeasurementChart key={kind} kind={kind} points={charts.data?.series[kind] ?? []} range={range} />
              ))}
            </div>
          </Suspense>
        </>
      ) : null}
      {list.data && total > 0 ? (
        <details className="measurement-list">
          <summary>Tutte le misurazioni ({total})</summary>
          <ul>
            {list.data.map((item) => (
              <li key={item.id}>
                <span>
                  {formatDate(item.measured_on)} · {MEASUREMENT_KINDS[item.kind]} · <strong>{formatMm(item.value_mm)}</strong>
                </span>
                <Button size="sm" variant="ghost" onClick={() => setEditing(item)}>
                  Modifica
                </Button>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      {editing ? (
        <MeasurementDialog
          plantId={plantId}
          measurement={editing === "new" ? null : editing}
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

interface DialogProps {
  plantId: number;
  measurement: Measurement | null;
  onClose: () => void;
  onSaved: () => void;
}

export function MeasurementDialog({ plantId, measurement, onClose, onSaved }: DialogProps) {
  const [kind, setKind] = useState<MeasurementKind>(measurement?.kind ?? "height");
  const [date, setDate] = useState(measurement?.measured_on ?? todayIso());
  const [unit, setUnit] = useState<LengthUnit>("mm");
  const [value, setValue] = useState(measurement ? String(Number(measurement.value_mm)) : "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const number = Number(value.replace(",", "."));
    if (!value.trim() || !Number.isFinite(number) || number <= 0) {
      setFieldError("Inserisci un valore maggiore di zero");
      return;
    }
    if (date > todayIso()) {
      setFieldError("La data non può essere nel futuro");
      return;
    }
    setFieldError(null);
    setBusy(true);
    setError(null);
    const payload = { kind, measured_on: date, value: String(number), unit };
    try {
      if (measurement) await measurements.update(measurement.id, payload);
      else await measurements.create(plantId, payload);
      onSaved();
    } catch (caught) {
      setError(caught);
      setBusy(false);
    }
  }

  async function remove() {
    if (!measurement) return;
    setBusy(true);
    try {
      await measurements.remove(measurement.id);
      onSaved();
    } catch (caught) {
      setError(caught);
      setBusy(false);
      setDeleting(false);
    }
  }

  return (
    <Dialog open title={measurement ? "Modifica misurazione" : "Nuova misurazione"} onClose={onClose}>
      <form className="form" onSubmit={submit} noValidate>
        <fieldset className="segmented segmented-small">
          <legend>Tipo di misura</legend>
          {Object.entries(MEASUREMENT_KINDS).map(([key, label]) => (
            <label key={key} className={kind === key ? "selected" : undefined}>
              <input type="radio" checked={kind === key} onChange={() => setKind(key as MeasurementKind)} />
              {label}
            </label>
          ))}
        </fieldset>
        {kind === "trunk_diameter" ? <p className="field-hint">Misurato con il calibro, alla base del tronco.</p> : null}
        <div className="form-row">
          <Field label="Valore" error={fieldError}>
            {(id, describedBy) => (
              <input
                id={id}
                aria-describedby={describedBy}
                inputMode="decimal"
                autoFocus
                value={value}
                onChange={(event) => setValue(event.target.value)}
              />
            )}
          </Field>
          <Field label="Unità" hint={unit === "cm" ? "Verrà convertito e mostrato in mm" : undefined}>
            {(id, describedBy) => (
              <select id={id} aria-describedby={describedBy} value={unit} onChange={(event) => setUnit(event.target.value as LengthUnit)}>
                {Object.entries(UNITS).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
            )}
          </Field>
        </div>
        <Field label="Data della rilevazione">
          {(id) => <input id={id} type="date" max={todayIso()} value={date} onChange={(event) => setDate(event.target.value)} />}
        </Field>
        <InlineError error={error} />
        <div className="form-actions">
          {measurement ? (
            <Button variant="ghost" className="text-danger push-left" onClick={() => setDeleting(true)}>
              Elimina
            </Button>
          ) : null}
          <Button variant="ghost" onClick={onClose}>
            Annulla
          </Button>
          <Button type="submit" variant="primary" busy={busy}>
            Salva
          </Button>
        </div>
      </form>
      <ConfirmDialog
        open={deleting}
        title="Eliminare la misurazione?"
        message="La misurazione verrà rimossa anche dal diario e dai grafici."
        confirmLabel="Elimina"
        danger
        busy={busy}
        onConfirm={remove}
        onCancel={() => setDeleting(false)}
      />
    </Dialog>
  );
}
