import { useEffect, useState } from "react";
import { Link } from "react-router";
import { agenda } from "../api/endpoints";
import type { Occurrence } from "../api/types";
import { EmptyState, ErrorState, Loading } from "../components/ui";
import { OccurrenceRow } from "../features/OccurrenceRow";
import { PlantSearch } from "../features/PlantSearch";
import { useTaskActions } from "../features/taskActions";
import { formatLongDate } from "../lib/format";
import { useAsync } from "../lib/useAsync";

const DAY_OPTIONS = [3, 7, 14, 31];
const STORAGE_KEY = "dashboard-days";

function storedDays(): number | undefined {
  try {
    const value = Number(window.localStorage.getItem(STORAGE_KEY));
    return DAY_OPTIONS.includes(value) ? value : undefined;
  } catch {
    return undefined;
  }
}

function storeDays(value: number): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, String(value));
  } catch {
    // preferenza non persistita: resta valida per la sessione corrente
  }
}

function Section({ title, items, tone }: { title: string; items: Occurrence[]; tone: string }) {
  if (!items.length) return null;
  return (
    <section className={`task-section task-section-${tone}`} aria-label={title}>
      <h2>
        {title} <span className="count">{items.length}</span>
      </h2>
      <ul className="occurrence-list">
        {items.map((item) => (
          <OccurrenceRow key={item.id} occurrence={item} />
        ))}
      </ul>
    </section>
  );
}

export function DashboardPage() {
  const [days, setDays] = useState<number | undefined>(storedDays);
  const { data, error, loading, reload } = useAsync(() => agenda.dashboard(days), [days]);
  const { onChange } = useTaskActions();

  useEffect(() => onChange(() => void reload()), [onChange, reload]);

  const empty = data && !data.overdue.length && !data.due_today.length && !data.upcoming.length;

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Oggi</h1>
          {data ? <p className="muted">{formatLongDate(data.today)}</p> : null}
        </div>
      </header>
      <PlantSearch />
      {error ? <ErrorState error={error} onRetry={reload} /> : null}
      {!data && loading ? <Loading /> : null}
      {data ? (
        <>
          <Section title="In ritardo" items={data.overdue} tone="overdue" />
          <Section title="Da fare oggi" items={data.due_today} tone="today" />
          <Section title={`Prossimi ${data.days} giorni`} items={data.upcoming} tone="upcoming" />
          {empty ? (
            <EmptyState title="Nessuna attività in programma" action={<Link to="/piante">Vai alle piante</Link>}>
              Non ci sono task in ritardo né in scadenza nei prossimi {data.days} giorni. Puoi creare i task dalla scheda di
              ogni pianta.
            </EmptyState>
          ) : null}
          <div className="days-picker">
            <label htmlFor="dashboard-days">Mostra i prossimi</label>
            <select
              id="dashboard-days"
              value={data.days}
              onChange={(event) => {
                const value = Number(event.target.value);
                storeDays(value);
                setDays(value);
              }}
            >
              {[...new Set([...DAY_OPTIONS, data.days])].sort((a, b) => a - b).map((option) => (
                <option key={option} value={option}>
                  {option} giorni
                </option>
              ))}
            </select>
          </div>
        </>
      ) : null}
    </div>
  );
}
