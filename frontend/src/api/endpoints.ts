import { request } from "./client";
import type {
  AppSettings,
  BackupStatus,
  ChartRange,
  CompleteResult,
  Dashboard,
  DiaryCategory,
  DiaryEntry,
  DiaryPage,
  DisplayStatus,
  Group,
  Measurement,
  MeasurementCharts,
  MeasurementInput,
  Occurrence,
  Plant,
  PlantInput,
  PlantStatus,
  PlantSummary,
  Session,
  Tag,
  Task,
  TaskInput,
  TaskType,
} from "./types";

export const auth = {
  me: () => request<Session>("GET", "/auth/me"),
  login: (username: string, password: string) =>
    request<Session>("POST", "/auth/login", { json: { username, password } }),
  logout: () => request<void>("POST", "/auth/logout"),
  changePassword: (current_password: string, new_password: string) =>
    request<void>("POST", "/auth/password", { json: { current_password, new_password } }),
};

export interface PlantFilters {
  q?: string;
  status?: PlantStatus | "all";
  group_id?: number | null;
  tag_id?: number | null;
  limit?: number;
}

export const plants = {
  list: (filters: PlantFilters = {}) => request<PlantSummary[]>("GET", "/plants", { query: { ...filters } }),
  get: (id: number) => request<Plant>("GET", `/plants/${id}`),
  create: (data: PlantInput) => request<Plant>("POST", "/plants", { json: data }),
  update: (id: number, data: PlantInput) => request<Plant>("PUT", `/plants/${id}`, { json: data }),
  archive: (id: number) => request<Plant>("POST", `/plants/${id}/archive`),
  restore: (id: number) => request<Plant>("POST", `/plants/${id}/restore`),
  remove: (id: number, confirm: string) => request<void>("DELETE", `/plants/${id}`, { query: { confirm } }),
};

export const groups = {
  list: () => request<Group[]>("GET", "/groups"),
  create: (name: string, description: string | null) =>
    request<Group>("POST", "/groups", { json: { name, description } }),
  update: (id: number, name: string, description: string | null) =>
    request<Group>("PUT", `/groups/${id}`, { json: { name, description } }),
  remove: (id: number) => request<void>("DELETE", `/groups/${id}`),
};

export interface TagInput {
  name: string;
  color: string | null;
  description: string | null;
}

export const tags = {
  list: () => request<Tag[]>("GET", "/tags"),
  create: (data: TagInput) => request<Tag>("POST", "/tags", { json: data }),
  update: (id: number, data: TagInput) => request<Tag>("PUT", `/tags/${id}`, { json: data }),
  remove: (id: number) => request<void>("DELETE", `/tags/${id}`),
};

export const tasks = {
  forPlant: (plantId: number) => request<Task[]>("GET", `/plants/${plantId}/tasks`),
  get: (id: number) => request<Task>("GET", `/tasks/${id}`),
  create: (plantId: number, data: TaskInput) => request<Task>("POST", `/plants/${plantId}/tasks`, { json: data }),
  update: (id: number, data: TaskInput) => request<Task>("PUT", `/tasks/${id}`, { json: data }),
  remove: (id: number) => request<void>("DELETE", `/tasks/${id}`),
  history: (id: number) => request<Occurrence[]>("GET", `/tasks/${id}/history`),
  suspend: (id: number, body: { days: number } | { until: string }) =>
    request<Task>("POST", `/tasks/${id}/suspend`, { json: body }),
  resume: (id: number) => request<Task>("POST", `/tasks/${id}/resume`),
  setActive: (id: number, active: boolean) => request<Task>("POST", `/tasks/${id}/active`, { json: { active } }),
};

export const occurrences = {
  complete: (id: number) => request<CompleteResult>("POST", `/occurrences/${id}/complete`, { json: {} }),
  skip: (id: number) => request<Occurrence>("POST", `/occurrences/${id}/skip`),
  reopen: (id: number) => request<Occurrence>("POST", `/occurrences/${id}/reopen`),
};

export interface CalendarFilters {
  plant_id?: number | null;
  group_id?: number | null;
  tag_id?: number | null;
  task_type?: TaskType | null;
  status?: DisplayStatus[];
}

export const agenda = {
  dashboard: (days?: number) => request<Dashboard>("GET", "/dashboard", { query: { days } }),
  calendar: (start: string, end: string, filters: CalendarFilters = {}) =>
    request<Occurrence[]>("GET", "/calendar", { query: { start, end, ...filters } }),
};

export interface NewEntry {
  body: string;
  category: DiaryCategory | "";
  occurred_at: string | null;
  files: File[];
}

export const diary = {
  list: (plantId: number, offset: number, limit = 20) =>
    request<DiaryPage>("GET", `/plants/${plantId}/diary`, { query: { offset, limit } }),
  create: (plantId: number, entry: NewEntry) => {
    const form = new FormData();
    if (entry.body.trim()) form.append("body", entry.body.trim());
    if (entry.category) form.append("category", entry.category);
    if (entry.occurred_at) form.append("occurred_at", entry.occurred_at);
    entry.files.forEach((file) => form.append("files", file));
    return request<DiaryEntry>("POST", `/plants/${plantId}/diary`, { form });
  },
  update: (id: number, data: { body: string | null; category: DiaryCategory | null; occurred_at?: string | null }) =>
    request<DiaryEntry>("PATCH", `/diary/${id}`, { json: data }),
  remove: (id: number) => request<void>("DELETE", `/diary/${id}`),
  addPhotos: (id: number, files: File[]) => {
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    return request<DiaryEntry>("POST", `/diary/${id}/photos`, { form });
  },
  removePhoto: (photoId: number) => request<void>("DELETE", `/photos/${photoId}`),
};

export const measurements = {
  list: (plantId: number) => request<Measurement[]>("GET", `/plants/${plantId}/measurements`),
  charts: (plantId: number, range: ChartRange) =>
    request<MeasurementCharts>("GET", `/plants/${plantId}/measurements/charts`, { query: { range } }),
  create: (plantId: number, data: MeasurementInput) =>
    request<Measurement>("POST", `/plants/${plantId}/measurements`, { json: data }),
  update: (id: number, data: MeasurementInput) => request<Measurement>("PUT", `/measurements/${id}`, { json: data }),
  remove: (id: number) => request<void>("DELETE", `/measurements/${id}`),
};

export const system = {
  settings: () => request<AppSettings>("GET", "/settings"),
  testTelegram: () => request<void>("POST", "/settings/telegram/test"),
  backups: () => request<BackupStatus>("GET", "/backups"),
  runBackup: () => request<BackupStatus>("POST", "/backups"),
};
