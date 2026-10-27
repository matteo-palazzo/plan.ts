import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Photo } from "../api/types";
import { Button, ConfirmDialog } from "../components/ui";

const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];
export const MAX_PHOTOS = 10;
export const MAX_PHOTO_MB = 15;

export function validatePhotos(files: File[], existing = 0, maxMb = MAX_PHOTO_MB): string | null {
  if (existing + files.length > MAX_PHOTOS) return `Puoi allegare al massimo ${MAX_PHOTOS} foto per voce`;
  const unsupported = files.find((file) => file.type && !ACCEPTED.includes(file.type));
  if (unsupported) return `Formato non supportato (${unsupported.name}): usa JPEG, PNG o WebP`;
  const tooBig = files.find((file) => file.size > maxMb * 1024 * 1024);
  if (tooBig) return `${tooBig.name} supera il limite di ${maxMb} MB`;
  return null;
}

interface PickerProps {
  files: File[];
  onChange: (files: File[]) => void;
  existing?: number;
}

export function PhotoPicker({ files, onChange, existing = 0 }: PickerProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const previews = useMemo(() => files.map((file) => URL.createObjectURL(file)), [files]);

  useEffect(() => () => previews.forEach((url) => URL.revokeObjectURL(url)), [previews]);

  function add(list: FileList | null) {
    const incoming = Array.from(list ?? []);
    const next = [...files, ...incoming];
    const problem = validatePhotos(next, existing);
    setError(problem);
    if (!problem) onChange(next);
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <div className="photo-picker">
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED.join(",")}
        multiple
        className="visually-hidden"
        id="photo-picker-input"
        onChange={(event) => add(event.target.files)}
      />
      {files.length ? (
        <ul className="photo-previews">
          {files.map((file, index) => (
            <li key={`${file.name}-${index}`}>
              <img src={previews[index]} alt={`Anteprima ${index + 1}`} />
              <button
                type="button"
                className="photo-remove"
                aria-label={`Rimuovi ${file.name}`}
                onClick={() => onChange(files.filter((_, position) => position !== index))}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {existing + files.length < MAX_PHOTOS ? (
        <Button onClick={() => inputRef.current?.click()}>📷 Aggiungi foto</Button>
      ) : null}
      <p className="field-hint">
        Fino a {MAX_PHOTOS} foto per voce, JPEG, PNG o WebP, massimo {MAX_PHOTO_MB} MB ciascuna.
      </p>
      {error ? (
        <p className="field-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

interface GalleryProps {
  photos: Photo[];
  onDelete?: (photo: Photo) => Promise<void>;
}

export function PhotoGallery({ photos, onDelete }: GalleryProps) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  if (!photos.length) return null;
  return (
    <>
      <ul className={`gallery gallery-${Math.min(photos.length, 3)}`}>
        {photos.map((photo, index) => (
          <li key={photo.id}>
            <button type="button" className="gallery-item" onClick={() => setOpenIndex(index)} aria-label={`Apri foto ${index + 1} di ${photos.length}`}>
              <img src={photo.url} alt="" loading="lazy" decoding="async" />
            </button>
          </li>
        ))}
      </ul>
      {openIndex !== null ? (
        <Lightbox photos={photos} start={openIndex} onClose={() => setOpenIndex(null)} onDelete={onDelete} />
      ) : null}
    </>
  );
}

interface LightboxProps {
  photos: Photo[];
  start: number;
  onClose: () => void;
  onDelete?: (photo: Photo) => Promise<void>;
}

function Lightbox({ photos, start, onClose, onDelete }: LightboxProps) {
  const [index, setIndex] = useState(start);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const touchStart = useRef<number | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const photo = photos[Math.min(index, photos.length - 1)];

  const move = useCallback(
    (step: number) => setIndex((current) => (current + step + photos.length) % photos.length),
    [photos.length],
  );

  useEffect(() => {
    closeRef.current?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (confirming) return;
      if (event.key === "Escape") onClose();
      if (event.key === "ArrowRight") move(1);
      if (event.key === "ArrowLeft") move(-1);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [move, onClose, confirming]);

  if (!photo) return null;

  async function remove() {
    if (!onDelete || !photo) return;
    setBusy(true);
    setError(null);
    try {
      await onDelete(photo);
      setConfirming(false);
      if (photos.length <= 1) onClose();
      else setIndex((current) => Math.min(current, photos.length - 2));
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="lightbox"
      role="dialog"
      aria-modal="true"
      aria-label={`Foto ${index + 1} di ${photos.length}`}
      onTouchStart={(event) => {
        touchStart.current = event.touches[0]?.clientX ?? null;
      }}
      onTouchEnd={(event) => {
        const startX = touchStart.current;
        const endX = event.changedTouches[0]?.clientX;
        touchStart.current = null;
        if (startX === null || endX === undefined) return;
        if (Math.abs(endX - startX) > 50) move(endX < startX ? 1 : -1);
      }}
    >
      <div className="lightbox-toolbar">
        <span>
          {index + 1} / {photos.length}
        </span>
        <div className="lightbox-actions">
          <a className="icon-button" href={photo.url} target="_blank" rel="noreferrer" aria-label="Apri originale in una nuova scheda">
            ⤢
          </a>
          {onDelete ? (
            <button type="button" className="icon-button" onClick={() => setConfirming(true)} aria-label="Elimina foto">
              🗑
            </button>
          ) : null}
          <button ref={closeRef} type="button" className="icon-button" onClick={onClose} aria-label="Chiudi">
            ✕
          </button>
        </div>
      </div>
      <img className="lightbox-image" src={photo.url} alt={`Foto ${index + 1}`} />
      {photos.length > 1 ? (
        <>
          <button type="button" className="lightbox-nav lightbox-prev" onClick={() => move(-1)} aria-label="Foto precedente">
            ‹
          </button>
          <button type="button" className="lightbox-nav lightbox-next" onClick={() => move(1)} aria-label="Foto successiva">
            ›
          </button>
        </>
      ) : null}
      <ConfirmDialog
        open={confirming}
        title="Eliminare la foto?"
        message="La foto verrà eliminata definitivamente dal server."
        confirmLabel="Elimina foto"
        danger
        busy={busy}
        error={error}
        onConfirm={remove}
        onCancel={() => setConfirming(false)}
      />
    </div>
  );
}
