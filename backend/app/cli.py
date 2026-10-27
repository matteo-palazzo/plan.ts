import argparse
import getpass
import json
import sys
from pathlib import Path

from sqlalchemy import func, select

from app.db import SessionLocal, engine
from app.models import Photo, User, UserSession
from app.security import MIN_PASSWORD_LENGTH, hash_password
from app.services import backup, notifications, photos


def _ask_password() -> str:
    while True:
        password = getpass.getpass("Password: ")
        if len(password) < MIN_PASSWORD_LENGTH:
            print(f"La password deve avere almeno {MIN_PASSWORD_LENGTH} caratteri.")
            continue
        if password != getpass.getpass("Ripeti la password: "):
            print("Le password non coincidono.")
            continue
        return password


def create_user(args) -> int:
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(User)):
            print("Esiste già un account. Usa 'reset-password' per cambiarne la password.", file=sys.stderr)
            return 1
        username = args.username or input("Nome utente: ").strip()
        if not username or len(username) > 64:
            print("Nome utente non valido.", file=sys.stderr)
            return 1
        db.add(User(username=username, password_hash=hash_password(_ask_password())))
        db.commit()
    print(f"Account '{username}' creato.")
    return 0


def reset_password(args) -> int:
    with SessionLocal() as db:
        user = db.scalars(select(User)).first()
        if user is None:
            print("Nessun account presente: usa 'create-user'.", file=sys.stderr)
            return 1
        print(f"Nuova password per '{user.username}'.")
        user.password_hash = hash_password(_ask_password())
        db.query(UserSession).filter(UserSession.user_id == user.id).delete()
        db.commit()
    print("Password aggiornata. Tutte le sessioni attive sono state chiuse.")
    return 0


def run_backup(args) -> int:
    path = backup.create_backup(engine)
    print(f"Backup creato: {path}")
    return 0


def backup_status(args) -> int:
    print(json.dumps(backup.read_status(), indent=2, ensure_ascii=False))
    for item in backup.list_backups():
        print(f"{item['name']}  {item['size_bytes'] / 1024 / 1024:.1f} MB")
    return 0


def restore(args) -> int:
    archive = Path(args.archive)
    if not archive.is_file():
        print(f"File non trovato: {archive}", file=sys.stderr)
        return 1
    manifest = backup.read_manifest(archive)
    print(f"Backup del {manifest['created_at']} (schema {manifest['schema_revision']}, {manifest['photo_count']} foto).")
    if args.force and not args.yes:
        answer = input("I dati attuali del database e la cartella delle foto verranno sostituiti. Scrivi 'ripristina' per continuare: ")
        if answer.strip() != "ripristina":
            print("Operazione annullata.")
            return 1
    result = backup.restore_backup(engine, archive, force=args.force)
    print(f"Ripristino completato: {sum(result['tables'].values())} righe, {result['photos']} foto.")
    return 0


def cleanup_orphans(args) -> int:
    with SessionLocal() as db:
        known = set(db.scalars(select(Photo.rel_path)))
    orphans = photos.find_orphan_files(known)
    for path in orphans:
        print(path)
        if args.delete:
            path.unlink(missing_ok=True)
    action = "eliminati" if args.delete else "trovati (usa --delete per eliminarli)"
    print(f"{len(orphans)} file orfani {action}.")
    return 0


def test_telegram(args) -> int:
    try:
        notifications.send_test_message()
    except notifications.TelegramError as exc:
        print(f"Invio non riuscito: {exc}", file=sys.stderr)
        return 1
    print("Messaggio di prova inviato.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Strumenti di amministrazione dell'app piante")
    commands = parser.add_subparsers(dest="command", required=True)

    sub = commands.add_parser("create-user", help="crea l'account amministratore (solo se non esiste)")
    sub.add_argument("--username")
    sub.set_defaults(handler=create_user)

    commands.add_parser("reset-password", help="imposta una nuova password").set_defaults(handler=reset_password)
    commands.add_parser("backup", help="esegue subito un backup").set_defaults(handler=run_backup)
    commands.add_parser("backup-status", help="mostra l'esito dell'ultimo backup").set_defaults(handler=backup_status)

    sub = commands.add_parser("restore", help="ripristina database e foto da un archivio di backup")
    sub.add_argument("archive")
    sub.add_argument("--force", action="store_true", help="sostituisce i dati esistenti")
    sub.add_argument("--yes", action="store_true", help="non chiede conferma")
    sub.set_defaults(handler=restore)

    sub = commands.add_parser("cleanup-orphans", help="cerca file di foto non collegati al database")
    sub.add_argument("--delete", action="store_true")
    sub.set_defaults(handler=cleanup_orphans)

    commands.add_parser("test-telegram", help="invia un messaggio di prova").set_defaults(handler=test_telegram)

    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except backup.BackupError as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
