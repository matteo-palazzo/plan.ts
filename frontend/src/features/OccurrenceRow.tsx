import { Link } from "react-router";
import type { Occurrence } from "../api/types";
import { StatusBadge } from "../components/ui";
import { TASK_TYPE_ICONS, formatDate, relativeDue } from "../lib/format";
import { useTaskActions } from "./taskActions";

interface Props {
  occurrence: Occurrence;
  showPlant?: boolean;
}

export function OccurrenceRow({ occurrence, showPlant = true }: Props) {
  const { complete, skip, busyId } = useTaskActions();
  const busy = busyId === occurrence.id;
  const actionable = occurrence.id !== null && (occurrence.status === "todo" || occurrence.status === "overdue");
  
  return (
    <li className={`occurrence occurrence-${occurrence.status}`}>
      <div className="occurrence-info">
        <div className="occurrence-cover">
          {occurrence.plant_cover_photo_id ? (
            <img src={`/api/photos/${occurrence.plant_cover_photo_id}/file`} alt="" loading="lazy" decoding="async" />
          ) : (
            <span aria-hidden="true">❦</span>
          )}
        </div>
        <span className="occurrence-icon" aria-hidden="true">
          {TASK_TYPE_ICONS[occurrence.task_type]}
        </span>
        <div>
          {showPlant ? (
            <Link className="occurrence-plant" to={`/piante/${occurrence.plant_id}`}>
              {occurrence.plant_name}
            </Link>
          ) : null}
          <p className="occurrence-task">{occurrence.task_name}</p>
          <p className="occurrence-due">
            <time dateTime={occurrence.due_date}>{formatDate(occurrence.due_date)}</time>
            <span className="muted"> · {relativeDue(occurrence.due_date)}</span>
            {occurrence.status === "overdue" || occurrence.status === "suspended" ? (
              <>
                {" "}
                <StatusBadge status={occurrence.status} />
              </>
            ) : null}
          </p>
        </div>
      </div>
      {actionable ? (
        <div className="occurrence-actions">
          <button
            type="button"
            className="btn btn-ghost btn-md action-skip"
            disabled={busy}
            onClick={() => void skip(occurrence)}
            aria-label={`Salta ${occurrence.task_name} di ${occurrence.plant_name}`}
          >
            <span aria-hidden="true">»</span> Salta
          </button>
          <button
            type="button"
            className="btn btn-success btn-md action-complete"
            disabled={busy}
            aria-busy={busy || undefined}
            onClick={() => void complete(occurrence)}
            aria-label={`Segna come fatto ${occurrence.task_name} di ${occurrence.plant_name}`}
          >
            <span aria-hidden="true">✓</span> Fatto
          </button>
        </div>
      ) : null}
    </li>
  );
}
