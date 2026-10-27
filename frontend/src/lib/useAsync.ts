import { useCallback, useEffect, useRef, useState } from "react";

export interface AsyncState<T> {
  data: T | undefined;
  error: unknown;
  loading: boolean;
  reload: () => Promise<void>;
  setData: (updater: T | ((current: T | undefined) => T)) => void;
}

export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setDataState] = useState<T>();
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const requestId = useRef(0);

  const run = useCallback(load, deps);

  const reload = useCallback(async () => {
    const id = ++requestId.current;
    setLoading(true);
    try {
      const result = await run();
      if (id === requestId.current) {
        setDataState(result);
        setError(null);
      }
    } catch (caught) {
      if (id === requestId.current) setError(caught);
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, [run]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const setData = useCallback((updater: T | ((current: T | undefined) => T)) => {
    setDataState((current) => (typeof updater === "function" ? (updater as (c: T | undefined) => T)(current) : updater));
  }, []);

  return { data, error, loading, reload, setData };
}
