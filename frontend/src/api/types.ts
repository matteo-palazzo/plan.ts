export type PlantStatus = "active" | "archived";
export type TaskType = "watering" | "fertilizing" | "repotting" | "pruning" | "check" | "other";
export type Recurrence = "once" | "interval" | "calendar";
export type NotifyMode = "none" | "day_of" | "day_before" | "both";
export type TaskStatus = "active" | "disabled";
export type DisplayStatus = "todo" | "overdue" | "completed" | "skipped" | "suspended" | "planned";
export type DiaryKind = "manual" | "task_completion" | "measurement";
export type DiaryCategory = "growth" | "health" | "pruning" | "repotting" | "fertilizing" | "watering" | "other";
export type MeasurementKind = "height" | "width" | "trunk_diameter";
export type LengthUnit = "mm" | "cm";
export type ChartRange = "month" | "year" | "all";

export interface Session {
  username: string;
  csrf_token: string;
}

export interface GroupRef {
  id: number;
  name: string;
}

export interface Group extends GroupRef {
  description: string | null;
  plant_count: number;
}

export interface TagRef {
  id: number;
  name: string;
  color: string | null;
}

export interface Tag extends TagRef {
  description: string | null;
  plant_count: number;
}

export interface PlantSummary {
  id: number;
  name: string;
  common_name: string | null;
  species: string | null;
  group: GroupRef | null;
  tags: TagRef[];
  status: PlantStatus;
  cover_photo_id: number | null;
}

export interface Plant extends PlantSummary {
  acquired_on: string | null;
  substrate: string | null;
  location: string | null;
  pot: string | null;
  style: string | null;
  notes: string | null;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PlantInput {
  name: string;
  common_name: string | null;
  species: string | null;
  acquired_on: string | null;
  substrate: string | null;
  location: string | null;
  pot: string | null;
  style: string | null;
  notes: string | null;
  group_id: number | null;
  tag_ids: number[];
}

export type CalendarRule = { kind: "weekly"; weekdays: number[] } | { kind: "monthly"; day: number };

export interface Occurrence {
  id: number | null;
  task_id: number;
  task_name: string;
  task_type: TaskType;
  plant_id: number;
  plant_name: string;
  due_date: string;
  status: DisplayStatus;
  completed_at: string | null;
  skipped_at: string | null;
}

export interface Task {
  id: number;
  plant_id: number;
  name: string;
  task_type: TaskType;
  description: string | null;
  recurrence: Recurrence;
  interval_days: number | null;
  calendar_rule: CalendarRule | null;
  start_date: string;
  end_date: string | null;
  notify: NotifyMode;
  status: TaskStatus;
  suspended_from: string | null;
  suspended_until: string | null;
  is_suspended: boolean;
  created_at: string;
  updated_at: string;
  pending: Occurrence[];
}

export interface TaskInput {
  name: string;
  task_type: TaskType;
  description: string | null;
  recurrence: Recurrence;
  interval_days: number | null;
  calendar_rule: CalendarRule | null;
  start_date: string;
  end_date: string | null;
  notify: NotifyMode;
}

export interface CompleteResult {
  occurrence: Occurrence;
  diary_entry_id: number;
  already_completed: boolean;
}

export interface Dashboard {
  today: string;
  days: number;
  overdue: Occurrence[];
  due_today: Occurrence[];
  upcoming: Occurrence[];
}

export interface Photo {
  id: number;
  mime_type: string;
  size_bytes: number;
  url: string;
  created_at: string;
}

export interface Measurement {
  id: number;
  plant_id: number;
  kind: MeasurementKind;
  measured_on: string;
  value_mm: string;
  input_unit: LengthUnit;
  created_at: string;
}

export interface MeasurementInput {
  kind: MeasurementKind;
  measured_on: string;
  value: string;
  unit: LengthUnit;
}

export interface ChartPoint {
  date: string;
  value_mm: string;
  measurement_id: number;
}

export interface MeasurementCharts {
  range: ChartRange;
  since: string | null;
  series: Record<MeasurementKind, ChartPoint[]>;
}

export interface DiaryEntry {
  id: number;
  plant_id: number;
  kind: DiaryKind;
  category: DiaryCategory | null;
  title: string | null;
  body: string | null;
  occurred_at: string;
  task_id: number | null;
  occurrence_id: number | null;
  photos: Photo[];
  measurement: Measurement | null;
}

export interface DiaryPage {
  items: DiaryEntry[];
  has_more: boolean;
}

export interface BackupInfo {
  name: string;
  size_bytes: number;
  created_at: string;
}

export interface BackupStatus {
  last_run_at: string | null;
  last_success_at: string | null;
  last_result: "success" | "error" | null;
  last_error: string | null;
  last_file: string | null;
  backups: BackupInfo[];
}

export interface AppSettings {
  version: string;
  timezone: string;
  dashboard_days: number;
  photo_max_mb: number;
  photos_per_entry: number;
  photo_formats: string[];
  notify_time: string;
  telegram: { enabled: boolean; configured: boolean };
  backup_schedule: string;
  backup_retention_days: number;
}
