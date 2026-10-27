import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { groups, plants, tags } from "../api/endpoints";
import type { PlantStatus } from "../api/types";
import { Button, Dialog, EmptyState, ErrorState, Field, InlineError, Loading, TagChip } from "../components/ui";
import { useAsync } from "../lib/useAsync";

export function PlantsPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const status = (params.get("stato") ?? "active") as PlantStatus | "all";
  const groupId = params.get("gruppo") ? Number(params.get("gruppo")) : null;
  const tagId = params.get("tag") ? Number(params.get("tag")) : null;
  const [creating, setCreating] = useState(false);

  const list = useAsync(
    () => plants.list({ q: q.trim() || undefined, status, group_id: groupId, tag_id: tagId }),
    [q, status, groupId, tagId],
  );
  const options = useAsync(() => Promise.all([groups.list(), tags.list()]), []);

  function update(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  }

  const filtered = Boolean(q || groupId || tagId || status !== "active");

  return (
    <div className="page">
      <header className="page-header">
        <h1>Piante</h1>
        <Button variant="primary" onClick={() => setCreating(true)}>
          + Nuova pianta
        </Button>
      </header>

      <div className="filters">
        <input
          type="search"
          aria-label="Cerca"
          placeholder="Cerca per nome, specie, gruppo o tag"
          value={q}
          onChange={(event) => update("q", event.target.value)}
        />
        <select aria-label="Gruppo" value={groupId ?? ""} onChange={(event) => update("gruppo", event.target.value)}>
          <option value="">Tutti i gruppi</option>
          {options.data?.[0].map((group) => (
            <option key={group.id} value={group.id}>
              {group.name}
            </option>
          ))}
        </select>
        <select aria-label="Tag" value={tagId ?? ""} onChange={(event) => update("tag", event.target.value)}>
          <option value="">Tutti i tag</option>
          {options.data?.[1].map((tag) => (
            <option key={tag.id} value={tag.id}>
              {tag.name}
            </option>
          ))}
        </select>
        <select
          aria-label="Stato"
          value={status}
          onChange={(event) => update("stato", event.target.value === "active" ? "" : event.target.value)}
        >
          <option value="active">Attive</option>
          <option value="archived">Archiviate</option>
          <option value="all">Tutte</option>
        </select>
      </div>

      {list.error ? <ErrorState error={list.error} onRetry={list.reload} /> : null}
      {!list.data && list.loading ? <Loading /> : null}
      {list.data && !list.data.length ? (
        filtered ? (
          <EmptyState title="Nessuna pianta corrisponde ai filtri" />
        ) : (
          <EmptyState
            title="Ancora nessuna pianta"
            action={
              <Button variant="primary" onClick={() => setCreating(true)}>
                Aggiungi la prima pianta
              </Button>
            }
          >
            Basta il nome: gli altri dettagli puoi aggiungerli quando vuoi.
          </EmptyState>
        )
      ) : null}
      {list.data?.length ? (
        <ul className="plant-grid">
          {list.data.map((plant) => (
            <li key={plant.id}>
              <Link to={`/piante/${plant.id}`} className="plant-card">
                <div className="plant-cover">
                  {plant.cover_photo_id ? (
                    <img src={`/api/photos/${plant.cover_photo_id}/file`} alt="" loading="lazy" decoding="async" />
                  ) : (
                    <span aria-hidden="true">❦</span>
                  )}
                </div>
                <div className="plant-card-body">
                  <h2>{plant.name}</h2>
                  {plant.species || plant.common_name ? (
                    <p className="muted plant-species">{plant.species ?? plant.common_name}</p>
                  ) : null}
                  <div className="chips">
                    {plant.status === "archived" ? <span className="chip chip-archived">Archiviata</span> : null}
                    {plant.group ? <span className="chip chip-group">{plant.group.name}</span> : null}
                    {plant.tags.map((tag) => (
                      <TagChip key={tag.id} name={tag.name} color={tag.color} />
                    ))}
                  </div>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}

      <CreatePlantDialog open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}

function CreatePlantDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      setError(new Error("Il nome è obbligatorio"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const plant = await plants.create({
        name: name.trim(),
        common_name: null,
        species: null,
        acquired_on: null,
        substrate: null,
        location: null,
        pot: null,
        style: null,
        notes: null,
        group_id: null,
        tag_ids: [],
      });
      navigate(`/piante/${plant.id}`);
    } catch (caught) {
      setError(caught);
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} title="Nuova pianta" onClose={onClose}>
      <form onSubmit={submit} className="form">
        <Field label="Nome" hint="Un nome che ti permetta di riconoscerla, ad esempio «Ginepro grande».">
          {(id, describedBy) => (
            <input
              id={id}
              aria-describedby={describedBy}
              autoFocus
              required
              maxLength={120}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          )}
        </Field>
        <InlineError error={error} />
        <div className="form-actions">
          <Button variant="ghost" onClick={onClose}>
            Annulla
          </Button>
          <Button type="submit" variant="primary" busy={busy}>
            Crea pianta
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
