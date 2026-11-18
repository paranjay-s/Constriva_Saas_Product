/** Whether the 3D builder can take plans, and the build qualities it names. Asked once; `reload` asks again. */
import { useCallback, useEffect, useState } from 'react';
import { plan3dApi, plan3dErrorText } from '../plan3dApi';
import type { Plan3dSystem } from '../plan3dSchemas';

interface Loaded {
  attempt: number;
  system: Plan3dSystem | null;
  error: string | null;
}

export function usePlan3dSystem() {
  const [attempt, setAttempt] = useState(0);
  const [loaded, setLoaded] = useState<Loaded | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    plan3dApi.system(controller.signal).then(
      (system) => {
        if (!controller.signal.aborted) setLoaded({ attempt, system, error: null });
      },
      (e: unknown) => {
        if (!controller.signal.aborted) setLoaded({ attempt, system: null, error: plan3dErrorText(e) });
      },
    );
    return () => controller.abort();
  }, [attempt]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);

  return {
    /** The last answer; kept on screen while it is asked for again. */
    system: loaded?.system ?? null,
    error: loaded?.error ?? null,
    loading: loaded?.attempt !== attempt,
    reload,
  };
}
