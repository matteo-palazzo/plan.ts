import { useState } from "react";
import { NavLink, Outlet, useOutletContext, useParams } from "react-router";
import { plants } from "../api/endpoints";
import type { Plant } from "../api/types";
import { useToast } from "../components/toast";
import { Button, ErrorState, Loading, TagChip } from "../components/ui";
import { errorMessage } from "../api/client";
import { useAsync } from "../lib/useAsync";

export interface PlantContext {
  plant: Plant;
  setPlant: (plant: Plant) => void;
}

export function usePlant(): PlantContext {
  return useOutletContext<PlantContext>();
}

export function PlantPage() {
  const { plantId } = useParams();
  const id = Number(plantId);
  const toast = useToast();
  const { data: plant, error, loading, reload, setData } = useAsync(() => plants.get(id), [id]);
  const [restoring, setRestoring] = useState(false);

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!plant || (loading && plant.id !== id)) return <Loading />;

  async function restore() {
    setRestoring(true);
    try {
      setData(await plants.restore(id));
      toast("Pianta ripristinata tra quelle attive", { tone: "success" });
    } catch (caught) {
      toast(errorMessage(caught), { tone: "error" });
    } finally {
      setRestoring(false);
    }
  }

  return (
    <div className="page plant-page">
      <header className="plant-header">
        <h1>{plant.name}</h1>
        {plant.species || plant.common_name ? (
          <p className="muted">{[plant.common_name, plant.species].filter(Boolean).join(" · ")}</p>
        ) : null}
        <div className="chips">
          {plant.group ? <span className="chip chip-group">{plant.group.name}</span> : null}
          {plant.tags.map((tag) => (
            <TagChip key={tag.id} name={tag.name} color={tag.color} />
          ))}
        </div>
        {plant.status === "archived" ? (
          <div className="banner banner-archived" role="status">
            <span>Pianta archiviata: non compare nelle liste operative e non genera promemoria.</span>
            <Button size="sm" busy={restoring} onClick={restore}>
              Ripristina
            </Button>
          </div>
        ) : null}
      </header>
      <nav className="tabs" aria-label="Sezioni della pianta">
        <NavLink end to={`/piante/${plant.id}`} className={({ isActive }) => `tab${isActive ? " active" : ""}`}>
          Diario
        </NavLink>
        <NavLink to={`/piante/${plant.id}/modifica`} className={({ isActive }) => `tab${isActive ? " active" : ""}`}>
          Modifica pianta
        </NavLink>
      </nav>
      <Outlet context={{ plant, setPlant: setData } satisfies PlantContext} />
    </div>
  );
}
