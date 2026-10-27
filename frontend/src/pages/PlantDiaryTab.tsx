import { useEffect, useState } from "react";
import type { Measurement } from "../api/types";
import { DiaryTimeline } from "../features/DiaryTimeline";
import { MeasurementDialog, MeasurementsPanel } from "../features/MeasurementsPanel";
import { TasksPanel } from "../features/TasksPanel";
import { useTaskActions } from "../features/taskActions";
import { usePlant } from "./PlantPage";

export function PlantDiaryTab() {
  const { plant } = usePlant();
  const { onChange } = useTaskActions();
  const [version, setVersion] = useState(0);
  const [measurement, setMeasurement] = useState<Measurement | null>(null);
  const bump = () => setVersion((current) => current + 1);

  useEffect(() => onChange(bump), [onChange]);

  return (
    <div className="plant-diary">
      <TasksPanel plantId={plant.id} archived={plant.status === "archived"} />
      <DiaryTimeline plantId={plant.id} version={version} onChanged={bump} onOpenMeasurement={setMeasurement} />
      <MeasurementsPanel plantId={plant.id} version={version} onChanged={bump} />
      {measurement ? (
        <MeasurementDialog
          plantId={plant.id}
          measurement={measurement}
          onClose={() => setMeasurement(null)}
          onSaved={() => {
            setMeasurement(null);
            bump();
          }}
        />
      ) : null}
    </div>
  );
}
