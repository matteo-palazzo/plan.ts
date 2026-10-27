import { useEffect, useId, useState } from "react";
import { useNavigate } from "react-router";
import { plants } from "../api/endpoints";
import type { PlantSummary } from "../api/types";

export function PlantSearch() {
  const navigate = useNavigate();
  const listId = useId();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PlantSummary[]>([]);
  const [active, setActive] = useState(0);
  const [searched, setSearched] = useState(false);

  useEffect(() => {
    const term = query.trim();
    if (!term) {
      setResults([]);
      setSearched(false);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      plants
        .list({ q: term, limit: 8 })
        .then((items) => {
          if (cancelled) return;
          setResults(items);
          setActive(0);
          setSearched(true);
        })
        .catch(() => {
          if (!cancelled) setResults([]);
        });
    }, 200);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query]);

  function open(plant: PlantSummary | undefined) {
    if (plant) navigate(`/piante/${plant.id}`);
  }

  const expanded = query.trim().length > 0 && searched;

  return (
    <div className="plant-search">
      <label htmlFor={`${listId}-input`} className="visually-hidden">
        Cerca una pianta
      </label>
      <input
        id={`${listId}-input`}
        type="search"
        placeholder="Cerca pianta per nome, specie, gruppo o tag"
        role="combobox"
        aria-expanded={expanded}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={expanded && results[active] ? `${listId}-${results[active].id}` : undefined}
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            setActive((current) => Math.min(current + 1, results.length - 1));
          } else if (event.key === "ArrowUp") {
            event.preventDefault();
            setActive((current) => Math.max(current - 1, 0));
          } else if (event.key === "Enter") {
            event.preventDefault();
            open(results[active]);
          } else if (event.key === "Escape") {
            setQuery("");
          }
        }}
      />
      {expanded ? (
        <ul id={listId} role="listbox" className="search-results">
          {results.length ? (
            results.map((plant, index) => (
              <li
                key={plant.id}
                id={`${listId}-${plant.id}`}
                role="option"
                aria-selected={index === active}
                className={index === active ? "active" : undefined}
                onMouseDown={(event) => {
                  event.preventDefault();
                  open(plant);
                }}
              >
                <span className="search-name">{plant.name}</span>
                <span className="search-meta">
                  {[plant.species ?? plant.common_name, plant.group?.name, ...plant.tags.map((tag) => tag.name)]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              </li>
            ))
          ) : (
            <li className="search-empty" role="option" aria-selected={false} aria-disabled>
              Nessuna pianta trovata
            </li>
          )}
        </ul>
      ) : null}
    </div>
  );
}
