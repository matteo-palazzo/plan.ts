export interface FieldError {
  field: string;
  message: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly fieldErrors: FieldError[];

  constructor(status: number, message: string, fieldErrors: FieldError[] = []) {
    super(message);
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

type QueryValue = string | number | boolean | null | undefined | Array<string | number>;

interface RequestOptions {
  query?: Record<string, QueryValue>;
  json?: unknown;
  form?: FormData;
}

let csrfToken: string | null = null;
let unauthorizedHandler: (() => void) | null = null;

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

export function onUnauthorized(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === null || value === undefined || value === "") continue;
    if (Array.isArray(value)) value.forEach((item) => params.append(key, String(item)));
    else params.append(key, String(value));
  }
  const search = params.toString();
  return `/api${path}${search ? `?${search}` : ""}`;
}

const FALLBACK_MESSAGES: Record<number, string> = {
  413: "I file sono troppo grandi per essere caricati",
  502: "Il server non risponde: riprova tra poco",
  503: "Servizio momentaneamente non disponibile",
  504: "Il server ha impiegato troppo tempo a rispondere",
};

async function toError(response: Response): Promise<ApiError> {
  let message = FALLBACK_MESSAGES[response.status] ?? `Errore imprevisto (${response.status})`;
  let fieldErrors: FieldError[] = [];
  try {
    const body = (await response.json()) as { detail?: unknown; errors?: FieldError[] };
    if (typeof body.detail === "string") message = body.detail;
    if (Array.isArray(body.errors)) fieldErrors = body.errors;
  } catch {
    // risposta non JSON: resta il messaggio generico
  }
  return new ApiError(response.status, message, fieldErrors);
}

export async function request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  let body: BodyInit | undefined;
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  } else if (options.form) {
    body = options.form;
  }
  if (method !== "GET" && csrfToken) headers["X-CSRF-Token"] = csrfToken;

  let response: Response;
  try {
    response = await fetch(buildUrl(path, options.query), {
      method,
      headers,
      body,
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError(0, "Connessione al server non riuscita: controlla la rete");
  }

  if (response.status === 401 && !path.startsWith("/auth/login")) {
    unauthorizedHandler?.();
  }
  if (!response.ok) throw await toError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Si è verificato un errore imprevisto";
}
