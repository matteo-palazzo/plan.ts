import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { agenda, groups, plants, tags } from "../api/endpoints";
import type { DisplayStatus, Occurrence, TaskType } from "../api/types";
import { Button, EmptyState, ErrorState, Loading, StatusBadge } from "../components/ui";
import { STATUS_ICONS, STATUS_LABELS, TASK_TYPES, TASK_TYPE_ICONS, WEEKDAYS_SHORT, formatLongDate, formatMonth, isoDate, todayIso } from "../lib/format";
import { useAsync } from "../lib/useAsync";

type View = "mese" | "agenda";

function monthBounds(month: Date) {
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const last = new Date(month.getFullYear(), month.getMonth() + 1, 0);
  const gridStart = new Date(first);
  gridStart.setDate(first.getDate() - ((first.getDay() + 6) % 7));
  const gridEnd = new Date(last);
  gridEnd.setDate(last.getDate() + (6 - ((last.getDay() + 6) % 7)));
  return { first, last, gridStart, gridEnd };
}

function parseMonth(value: string | null): Date {
  const match = value?.match(/^(\d{4})-(\d{2})$/);
  if (match) return new Date(Number(match[1]), Number(match[2]) - 1, 1);
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), 1);
}

function monthParam(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

const STATUS_FILTERS: DisplayStatus[] = ["todo", "overdue", "completed", "skipped", "suspended"];

export function CalendarPage() {
  const [params, setParams] = useSearchParams();
  const view: View = params.get("vista") === "agenda" ? "agenda" : "mese";
  const month = parseMonth(params.get("mese"));
  const plantId = params.get("pianta") ? Number(params.get("pianta")) : null;
  const groupId = params.get("gruppo") ? Number(params.get("gruppo")) : null;
  const tagId = params.get("tag") ? Number(params.get("tag")) : null;
  const taskType = (params.get("tipo") as TaskType | null) || null;
  const status = (params.get("stato") as DisplayStatus | null) || null;
  const [selectedDay, setSelectedDay] = useState<string | null>(null);

  const bounds = monthBounds(month);
  const start = isoDate(view === "mese" ? bounds.gridStart : bounds.first);
  const end = isoDate(view === "mese" ? bounds.gridEnd : bounds.last);

  const items = useAsync(
    () =>
      agenda.calendar(start, end, {
        plant_id: plantId,
        group_id: groupId,
        tag_id: tagId,
        task_type: taskType,
        status: status ? [status] : undefined,
      }),
    [start, end, plantId, groupId, tagId, taskType, status],
  );
  const options = useAsync(() => Promise.all([plants.list({ status: "all" }), groups.list(), tags.list()]), []);

  const byDay = useMemo(() => {
    const map = new Map<string, Occurrence[]>();
    for (const item of items.data ?? []) {
      const list = map.get(item.due_date) ?? [];
      list.push(item);
      map.set(item.due_date, list);
    }
    return map;
  }, [items.data]);

  function update(changes: Record<string, string | null>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    setParams(next, { replace: true });
  }

  function shiftMonth(step: number) {
    setSelectedDay(null);
    update({ mese: monthParam(new Date(month.getFullYear(), month.getMonth() + step, 1)) });
  }

  const today = todayIso();
  const days: Date[] = [];
  for (let day = new Date(bounds.gridStart); day <= bounds.gridEnd; day.setDate(day.getDate() + 1)) days.push(new Date(day));
  const filtersActive = Boolean(plantId || groupId || tagId || taskType || status);

  return (
    <div className="page calendar-page">
      <header className="page-header">
        <h1>Calendario</h1>
        <div className="segmented segmented-small" role="group" aria-label="Vista">
          {(["mese", "agenda"] as View[]).map((option) => (
            <button
              key={option}
              type="button"
              className={view === option ? "selected" : undefined}
              aria-pressed={view === option}
              onClick={() => update({ vista: option === "mese" ? null : option })}
            >
              {option === "mese" ? "Mese" : "Agenda"}
            </button>
          ))}
        </div>
      </header>

      <details className="filters-panel" open={filtersActive || undefined}>
        <summary>Filtri{filtersActive ? " (attivi)" : ""}</summary>
        <div className="filters">
          <select aria-label="Pianta" value={plantId ?? ""} onChange={(event) => update({ pianta: event.target.value })}>
            <option value="">Tutte le piante</option>
            {options.data?.[0].map((plant) => (
              <option key={plant.id} value={plant.id}>
                {plant.name}
                {plant.status === "archived" ? " (archiviata)" : ""}
              </option>
            ))}
          </select>
          <select aria-label="Gruppo" value={groupId ?? ""} onChange={(event) => update({ gruppo: event.target.value })}>
            <option value="">Tutti i gruppi</option>
            {options.data?.[1].map((group) => (
              <option key={group.id} value={group.id}>
                {group.name}
              </option>
            ))}
          </select>
          <select aria-label="Tag" value={tagId ?? ""} onChange={(event) => update({ tag: event.target.value })}>
            <option value="">Tutti i tag</option>
            {options.data?.[2].map((tag) => (
              <option key={tag.id} value={tag.id}>
                {tag.name}
              </option>
            ))}
          </select>
          <select aria-label="Tipologia" value={taskType ?? ""} onChange={(event) => update({ tipo: event.target.value })}>
            <option value="">Tutte le tipologie</option>
            {Object.entries(TASK_TYPES).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
          <select aria-label="Stato" value={status ?? ""} onChange={(event) => update({ stato: event.target.value })}>
            <option value="">Tutti gli stati</option>
            {STATUS_FILTERS.map((key) => (
              <option key={key} value={key}>
                {STATUS_LABELS[key]}
              </option>
            ))}
          </select>
          {filtersActive ? (
            <Button size="sm" variant="ghost" onClick={() => update({ pianta: null, gruppo: null, tag: null, tipo: null, stato: null })}>
              Azzera filtri
            </Button>
          ) : null}
        </div>
      </details>

      <div className="month-nav">
        <Button size="sm" onClick={() => shiftMonth(-1)} aria-label="Mese precedente">
          ‹
        </Button>
        <h2>{formatMonth(month)}</h2>
        <Button size="sm" onClick={() => shiftMonth(1)} aria-label="Mese successivo">
          ›
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            setSelectedDay(today);
            update({ mese: null });
          }}
        >
          Oggi
        </Button>
      </div>

      <Legend />

      {items.error ? <ErrorState error={items.error} onRetry={items.reload} /> : null}
      {!items.data && items.loading ? <Loading /> : null}

      {items.data && view === "mese" ? (
        <>
          <div className="month-grid" role="grid" aria-label={formatMonth(month)}>
            <div role="row" className="month-row month-head">
              {WEEKDAYS_SHORT.map((label) => (
                <div role="columnheader" key={label}>
                  {label}
                </div>
              ))}
            </div>
            {Array.from({ length: days.length / 7 }, (_, week) => (
              <div role="row" className="month-row" key={week}>
                {days.slice(week * 7, week * 7 + 7).map((day) => {
                  const key = isoDate(day);
                  const entries = byDay.get(key) ?? [];
                  const outside = day.getMonth() !== month.getMonth();
                  return (
                    <div role="gridcell" key={key} aria-selected={selectedDay === key}>
                      <button
                        type="button"
                        className={`day${outside ? " day-outside" : ""}${key === today ? " day-today" : ""}${selectedDay === key ? " day-selected" : ""}`}
                        onClick={() => setSelectedDay(key)}
                        aria-label={`${formatLongDate(key)}: ${entries.length ? `${entries.length} attività` : "nessuna attività"}`}
                      >
                        <span className="day-number">{day.getDate()}</span>
                        <span className="day-items" aria-hidden="true">
                          {entries.slice(0, 3).map((entry, index) => (
                            <span key={`${entry.task_id}-${index}`} className={`day-pill pill-${entry.status}`}>
                              <span className="pill-icon">{STATUS_ICONS[entry.status]}</span>
                              <span className="pill-text">{entry.plant_name}</span>
                            </span>
                          ))}
                          {entries.length > 3 ? <span className="day-more">+{entries.length - 3}</span> : null}
                        </span>
                      </button>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
          {selectedDay ? (
            <section className="day-detail" aria-label={`Attività del ${formatLongDate(selectedDay)}`}>
              <h3>{formatLongDate(selectedDay)}</h3>
              <AgendaList items={byDay.get(selectedDay) ?? []} />
            </section>
          ) : (
            <p className="muted center small">Tocca un giorno per vederne le attività.</p>
          )}
        </>
      ) : null}

      {items.data && view === "agenda" ? (
        items.data.length ? (
          <div className="agenda">
            {[...byDay.entries()].map(([day, entries]) => (
              <section key={day} className={`agenda-day${day === today ? " agenda-today" : ""}`}>
                <h3>{formatLongDate(day)}</h3>
                <AgendaList items={entries} />
              </section>
            ))}
          </div>
        ) : (
          <EmptyState title="Nessuna attività in questo mese" />
        )
      ) : null}
    </div>
  );
}

function AgendaList({ items }: { items: Occurrence[] }) {
  if (!items.length) return <p className="muted">Nessuna attività.</p>;
  return (
    <ul className="agenda-list">
      {items.map((item, index) => (
        <li key={item.id ?? `p-${item.task_id}-${index}`}>
          <Link to={`/piante/${item.plant_id}`} className={`agenda-item status-${item.status}`}>
            <span aria-hidden="true">{TASK_TYPE_ICONS[item.task_type]}</span>
            <span className="agenda-text">
              <strong>{item.task_name}</strong>
              <span className="muted">{item.plant_name}</span>
            </span>
            <StatusBadge status={item.status} />
          </Link>
        </li>
      ))}
    </ul>
  );
}

function Legend() {
  return (
    <ul className="legend" aria-label="Legenda degli stati">
      {(["todo", "overdue", "completed", "skipped", "suspended", "planned"] as DisplayStatus[]).map((key) => (
        <li key={key}>
          <span className={`day-pill pill-${key}`}>
            <span className="pill-icon" aria-hidden="true">
              {STATUS_ICONS[key]}
            </span>
          </span>
          {STATUS_LABELS[key]}
        </li>
      ))}
    </ul>
  );
}
