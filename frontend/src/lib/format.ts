import type {
  DiaryCategory,
  DisplayStatus,
  LengthUnit,
  MeasurementKind,
  NotifyMode,
  Recurrence,
  TaskType,
  CalendarRule,
} from "../api/types";

export const TASK_TYPES: Record<TaskType, string> = {
  watering: "Innaffiatura",
  fertilizing: "Fertilizzazione",
  repotting: "Rinvaso",
  pruning: "Potatura",
  check: "Controllo",
  other: "Altro",
};

export const TASK_TYPE_ICONS: Record<TaskType, string> = {
  watering: "💧",
  fertilizing: "🧪",
  repotting: "🪴",
  pruning: "✂️",
  check: "🔍",
  other: "📌",
};

export const RECURRENCES: Record<Recurrence, string> = {
  once: "Una tantum",
  interval: "A intervallo",
  calendar: "A calendario",
};

export const NOTIFY_MODES: Record<NotifyMode, string> = {
  none: "Nessuna notifica",
  day_of: "Il giorno della scadenza",
  day_before: "Il giorno prima",
  both: "Giorno prima e giorno della scadenza",
};

export const STATUS_LABELS: Record<DisplayStatus, string> = {
  todo: "Da fare",
  overdue: "In ritardo",
  completed: "Completato",
  skipped: "Saltato",
  suspended: "Sospeso",
  planned: "Previsto",
};

export const STATUS_ICONS: Record<DisplayStatus, string> = {
  todo: "○",
  overdue: "!",
  completed: "✓",
  skipped: "»",
  suspended: "Ⅱ",
  planned: "·",
};

export const DIARY_CATEGORIES: Record<DiaryCategory, string> = {
  growth: "Crescita",
  health: "Salute",
  pruning: "Potatura",
  repotting: "Rinvaso",
  fertilizing: "Concimazione",
  watering: "Irrigazione",
  other: "Altro",
};

export const MEASUREMENT_KINDS: Record<MeasurementKind, string> = {
  height: "Altezza",
  width: "Larghezza",
  trunk_diameter: "Diametro del tronco",
};

export const UNITS: Record<LengthUnit, string> = { mm: "mm", cm: "cm" };

export const WEEKDAYS = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"];
export const WEEKDAYS_SHORT = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"];

export function parseDate(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year ?? 1970, (month ?? 1) - 1, day ?? 1);
}

export function isoDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

export function todayIso(): string {
  return isoDate(new Date());
}

export function addDays(value: string, days: number): string {
  const date = parseDate(value);
  date.setDate(date.getDate() + days);
  return isoDate(date);
}

export function daysBetween(from: string, to: string): number {
  return Math.round((parseDate(to).getTime() - parseDate(from).getTime()) / 86_400_000);
}

const dateFormatter = new Intl.DateTimeFormat("it-IT", { weekday: "short", day: "numeric", month: "short" });
const longDateFormatter = new Intl.DateTimeFormat("it-IT", { day: "numeric", month: "long", year: "numeric" });
const dateTimeFormatter = new Intl.DateTimeFormat("it-IT", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});
const monthFormatter = new Intl.DateTimeFormat("it-IT", { month: "long", year: "numeric" });

export function formatDate(value: string): string {
  return dateFormatter.format(parseDate(value));
}

export function formatLongDate(value: string): string {
  return longDateFormatter.format(parseDate(value));
}

export function formatDateTime(value: string): string {
  return dateTimeFormatter.format(new Date(value));
}

export function formatMonth(date: Date): string {
  const label = monthFormatter.format(date);
  return label.charAt(0).toUpperCase() + label.slice(1);
}

export function relativeDue(due: string, today: string = todayIso()): string {
  const diff = daysBetween(today, due);
  if (diff === 0) return "oggi";
  if (diff === 1) return "domani";
  if (diff === -1) return "ieri";
  if (diff < 0) return `${-diff} giorni fa`;
  return `tra ${diff} giorni`;
}

export function toLocalInput(value: Date): string {
  const offset = value.getTimezoneOffset() * 60_000;
  return new Date(value.getTime() - offset).toISOString().slice(0, 16);
}

export function fromLocalInput(value: string): string {
  return new Date(value).toISOString();
}

export function formatMm(value: string | number): string {
  const number = typeof value === "string" ? Number(value) : value;
  return `${number.toLocaleString("it-IT", { maximumFractionDigits: 2 })} mm`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toLocaleString("it-IT", { maximumFractionDigits: 1 })} MB`;
}

export function describeRecurrence(recurrence: Recurrence, intervalDays: number | null, rule: CalendarRule | null): string {
  if (recurrence === "once") return "Una tantum";
  if (recurrence === "interval") return intervalDays === 1 ? "Ogni giorno" : `Ogni ${intervalDays} giorni`;
  if (!rule) return "A calendario";
  if (rule.kind === "weekly") {
    if (rule.weekdays.length === 7) return "Tutti i giorni";
    return `Ogni ${rule.weekdays.map((day) => WEEKDAYS[day]?.toLowerCase()).join(", ")}`;
  }
  return `Il giorno ${rule.day} di ogni mese`;
}
