import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { ApiError } from "../api/client";
import { groups, plants, tags } from "../api/endpoints";
import type { Plant, PlantInput } from "../api/types";
import { useToast } from "../components/toast";
import { Button, Dialog, ErrorState, Field, InlineError, Loading } from "../components/ui";
import { formatDateTime } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import { usePlant } from "./PlantPage";

type TextField = "name" | "common_name" | "species" | "acquired_on" | "substrate" | "location" | "pot" | "style" | "notes";

function toForm(plant: Plant) {
  return {
    name: plant.name,
    common_name: plant.common_name ?? "",
    species: plant.species ?? "",
    acquired_on: plant.acquired_on ?? "",
    substrate: plant.substrate ?? "",
    location: plant.location ?? "",
    pot: plant.pot ?? "",
    style: plant.style ?? "",
    notes: plant.notes ?? "",
    group_id: plant.group?.id ?? null,
    tag_ids: plant.tags.map((tag) => tag.id),
  };
}

export function PlantEditTab() {
  const { plant, setPlant } = usePlant();
  const toast = useToast();
  const options = useAsync(() => Promise.all([groups.list(), tags.list()]), []);
  const [form, setForm] = useState(() => toForm(plant));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [newGroup, setNewGroup] = useState("");
  const [newTag, setNewTag] = useState("");
  const [optionError, setOptionError] = useState<unknown>(null);

  function setText(key: TextField, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!form.name.trim()) {
      setErrors({ name: "Il nome è obbligatorio" });
      return;
    }
    setErrors({});
    setBusy(true);
    setError(null);
    const blank = (value: string) => value.trim() || null;
    const payload: PlantInput = {
      name: form.name.trim(),
      common_name: blank(form.common_name),
      species: blank(form.species),
      acquired_on: form.acquired_on || null,
      substrate: blank(form.substrate),
      location: blank(form.location),
      pot: blank(form.pot),
      style: blank(form.style),
      notes: blank(form.notes),
      group_id: form.group_id,
      tag_ids: form.tag_ids,
    };
    try {
      const saved = await plants.update(plant.id, payload);
      setPlant(saved);
      setForm(toForm(saved));
      toast("Scheda salvata", { tone: "success" });
    } catch (caught) {
      if (caught instanceof ApiError) {
        setErrors(Object.fromEntries(caught.fieldErrors.map((item) => [item.field, item.message])));
      }
      setError(caught);
    } finally {
      setBusy(false);
    }
  }

  async function addGroup() {
    if (!newGroup.trim()) return;
    setOptionError(null);
    try {
      const group = await groups.create(newGroup.trim(), null);
      await options.reload();
      setForm((current) => ({ ...current, group_id: group.id }));
      setNewGroup("");
    } catch (caught) {
      setOptionError(caught);
    }
  }

  async function addTag() {
    if (!newTag.trim()) return;
    setOptionError(null);
    try {
      const tag = await tags.create({ name: newTag.trim(), color: null, description: null });
      await options.reload();
      setForm((current) => ({ ...current, tag_ids: [...current.tag_ids, tag.id] }));
      setNewTag("");
    } catch (caught) {
      setOptionError(caught);
    }
  }

  const textFields: { key: TextField; label: string; multiline?: boolean; placeholder?: string }[] = [
    { key: "common_name", label: "Nome comune" },
    { key: "species", label: "Specie botanica", placeholder: "es. Juniperus chinensis" },
    { key: "location", label: "Posizione" },
    { key: "pot", label: "Vaso", multiline: true, placeholder: "Materiale, dimensioni, forma…" },
    { key: "substrate", label: "Substrato e composizione", multiline: true, placeholder: "es. Akadama 60%, pomice 20%, lapillo 20%" },
    { key: "style", label: "Stile e obiettivi di coltivazione", multiline: true },
  ];

  return (
    <div className="plant-edit">
      <form className="form panel" onSubmit={submit} noValidate>
        <Field label="Nome" error={errors.name}>
          {(id, describedBy) => (
            <input id={id} aria-describedby={describedBy} required maxLength={120} value={form.name} onChange={(event) => setText("name", event.target.value)} />
          )}
        </Field>
        <div className="form-grid">
          {textFields.map((field) => (
            <Field key={field.key} label={field.label} error={errors[field.key]}>
              {(id, describedBy) =>
                field.multiline ? (
                  <textarea
                    id={id}
                    aria-describedby={describedBy}
                    rows={2}
                    maxLength={5000}
                    placeholder={field.placeholder}
                    value={form[field.key]}
                    onChange={(event) => setText(field.key, event.target.value)}
                  />
                ) : (
                  <input
                    id={id}
                    aria-describedby={describedBy}
                    maxLength={200}
                    placeholder={field.placeholder}
                    value={form[field.key]}
                    onChange={(event) => setText(field.key, event.target.value)}
                  />
                )
              }
            </Field>
          ))}
          <Field label="Data di acquisizione" error={errors.acquired_on}>
            {(id) => <input id={id} type="date" value={form.acquired_on} onChange={(event) => setText("acquired_on", event.target.value)} />}
          </Field>
        </div>
        <Field label="Note permanenti" hint="Informazioni stabili sulla pianta. Non compaiono nel diario.">
          {(id, describedBy) => (
            <textarea id={id} aria-describedby={describedBy} rows={5} maxLength={20000} value={form.notes} onChange={(event) => setText("notes", event.target.value)} />
          )}
        </Field>

        {options.error ? <ErrorState error={options.error} onRetry={options.reload} /> : null}
        {!options.data && options.loading ? <Loading /> : null}
        {options.data ? (
          <>
            <div className="form-row align-end">
              <Field label="Gruppo">
                {(id) => (
                  <select
                    id={id}
                    value={form.group_id ?? ""}
                    onChange={(event) => setForm((current) => ({ ...current, group_id: event.target.value ? Number(event.target.value) : null }))}
                  >
                    <option value="">Nessun gruppo</option>
                    {options.data?.[0].map((group) => (
                      <option key={group.id} value={group.id}>
                        {group.name}
                      </option>
                    ))}
                  </select>
                )}
              </Field>
              <div className="inline-create">
                <input aria-label="Nuovo gruppo" placeholder="Nuovo gruppo" maxLength={100} value={newGroup} onChange={(event) => setNewGroup(event.target.value)} />
                <Button size="sm" onClick={addGroup} disabled={!newGroup.trim()}>
                  Crea
                </Button>
              </div>
            </div>
            <fieldset className="tag-picker">
              <legend>Tag</legend>
              <div className="chips">
                {options.data[1].map((tag) => {
                  const selected = form.tag_ids.includes(tag.id);
                  return (
                    <label key={tag.id} className={`chip chip-toggle${selected ? " selected" : ""}`} style={tag.color ? { borderColor: tag.color } : undefined}>
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() =>
                          setForm((current) => ({
                            ...current,
                            tag_ids: selected ? current.tag_ids.filter((item) => item !== tag.id) : [...current.tag_ids, tag.id],
                          }))
                        }
                      />
                      {selected ? "✓ " : ""}
                      {tag.name}
                    </label>
                  );
                })}
                {!options.data[1].length ? <span className="muted">Nessun tag ancora.</span> : null}
              </div>
              <div className="inline-create">
                <input aria-label="Nuovo tag" placeholder="Nuovo tag" maxLength={50} value={newTag} onChange={(event) => setNewTag(event.target.value)} />
                <Button size="sm" onClick={addTag} disabled={!newTag.trim()}>
                  Crea
                </Button>
              </div>
            </fieldset>
            <InlineError error={optionError} />
          </>
        ) : null}

        <InlineError error={error} />
        <div className="form-actions sticky-actions">
          <Button type="submit" variant="primary" busy={busy}>
            Salva modifiche
          </Button>
        </div>
        <p className="muted small">
          Creata il {formatDateTime(plant.created_at)} · ultima modifica {formatDateTime(plant.updated_at)}
        </p>
      </form>
      <DangerZone plant={plant} onChange={setPlant} />
    </div>
  );
}

function DangerZone({ plant, onChange }: { plant: Plant; onChange: (plant: Plant) => void }) {
  const navigate = useNavigate();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmName, setConfirmName] = useState("");
  const [error, setError] = useState<unknown>(null);

  async function toggleArchive() {
    setBusy(true);
    setError(null);
    try {
      const updated = plant.status === "archived" ? await plants.restore(plant.id) : await plants.archive(plant.id);
      onChange(updated);
      toast(updated.status === "archived" ? "Pianta archiviata" : "Pianta ripristinata", { tone: "success" });
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await plants.remove(plant.id, confirmName);
      toast(`«${plant.name}» eliminata definitivamente`, { tone: "success" });
      navigate("/piante", { replace: true });
    } catch (caught) {
      setError(caught);
      setBusy(false);
    }
  }

  return (
    <section className="panel danger-zone" aria-labelledby="danger-title">
      <h2 id="danger-title">Archiviazione ed eliminazione</h2>
      <div className="danger-row">
        <p>
          {plant.status === "archived"
            ? "La pianta è archiviata. Ripristinandola tornerà nelle liste e i suoi task riprenderanno."
            : "Archiviando la pianta la nascondi dalle liste e sospendi task e promemoria. Diario, foto e misurazioni restano."}
        </p>
        <Button busy={busy && !deleting} onClick={toggleArchive}>
          {plant.status === "archived" ? "Ripristina" : "Archivia"}
        </Button>
      </div>
      <div className="danger-row">
        <p>Eliminazione definitiva di pianta, diario, foto, misurazioni e task. Non si può annullare.</p>
        <Button variant="danger" onClick={() => setDeleting(true)}>
          Elimina…
        </Button>
      </div>
      {!deleting ? <InlineError error={error} /> : null}
      <Dialog
        open={deleting}
        title="Eliminare definitivamente?"
        onClose={() => setDeleting(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleting(false)}>
              Annulla
            </Button>
            <Button variant="danger" busy={busy} disabled={confirmName.trim() !== plant.name} onClick={remove}>
              Elimina per sempre
            </Button>
          </>
        }
      >
        <p>
          Verranno eliminati <strong>{plant.name}</strong>, tutte le voci del diario, le foto (anche i file sul disco), le
          misurazioni, i task e il loro storico. Se vuoi solo nasconderla, usa «Archivia».
        </p>
        <Field label={`Per confermare scrivi «${plant.name}»`}>
          {(id) => <input id={id} autoComplete="off" value={confirmName} onChange={(event) => setConfirmName(event.target.value)} />}
        </Field>
        <InlineError error={error} />
      </Dialog>
    </section>
  );
}
