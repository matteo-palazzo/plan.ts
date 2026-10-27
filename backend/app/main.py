import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError

from app.api import agenda, auth, journal, plants, system, tasks
from app.config import APP_VERSION, get_settings
from app.errors import AppError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logger = logging.getLogger("app")

VALIDATION_MESSAGES = {
    "missing": "Campo obbligatorio",
    "string_too_short": "Campo obbligatorio",
    "string_too_long": "Testo troppo lungo",
    "date_from_datetime_parsing": "Data non valida",
    "date_parsing": "Data non valida",
    "datetime_parsing": "Data e ora non valide",
    "datetime_from_date_parsing": "Data e ora non valide",
    "int_parsing": "Numero intero non valido",
    "decimal_parsing": "Numero non valido",
    "greater_than": "Il valore deve essere maggiore di zero",
    "less_than_equal": "Valore troppo grande",
    "enum": "Valore non ammesso",
    "literal_error": "Valore non ammesso",
    "string_pattern_mismatch": "Formato non valido",
}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    scheduler = None
    if get_settings().scheduler_enabled:
        from app.scheduler import start_scheduler

        scheduler = start_scheduler()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="Piante",
    version=APP_VERSION,
    description="API per la gestione di una collezione personale di piante.",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError):
    return JSONResponse({"detail": exc.message}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        location = [str(part) for part in error.get("loc", ()) if part not in ("body", "query", "path")]
        if error.get("type") == "value_error":
            message = str(error.get("ctx", {}).get("error", error.get("msg")))
        else:
            message = VALIDATION_MESSAGES.get(error.get("type"), error.get("msg"))
        errors.append({"field": ".".join(location), "message": message})
    summary = errors[0]["message"] if len(errors) == 1 else "Alcuni campi non sono validi"
    return JSONResponse({"detail": summary, "errors": errors}, status_code=422)


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, _exc: IntegrityError):
    logger.warning("Violazione di vincolo del database su %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Operazione in conflitto con dati esistenti"}, status_code=409)


@app.exception_handler(OperationalError)
async def database_error_handler(_request: Request, _exc: OperationalError):
    logger.error("Database non raggiungibile o errore operativo")
    return JSONResponse({"detail": "Database momentaneamente non raggiungibile"}, status_code=503)


@app.exception_handler(OSError)
async def filesystem_error_handler(_request: Request, exc: OSError):
    logger.error("Errore del filesystem: %s", type(exc).__name__)
    return JSONResponse({"detail": "Errore di accesso ai file sul server"}, status_code=500)


for module in (auth, plants, tasks, journal, agenda, system):
    app.include_router(module.router, prefix="/api")
