/**
 * Lets a page that renders the shell drive the background and the history with plain
 * props: working, a pulse / dim counter, the plan's facing, and a history counter.
 */
import { useEffect, useRef } from 'react';
import { useOcean } from './ocean/OceanBackground';
import { useStudio } from './StudioShell';

export interface Signals {
  working: boolean;
  pulse: number;
  dim: number;
  facing?: string | null;
  history: number;
}

export function StudioSync({ working, pulse, dim, facing, history }: Signals) {
  const ocean = useOcean();
  const { refreshHistory } = useStudio();
  const first = useRef({ pulse, dim, history });

  useEffect(() => {
    ocean.setWorking(working);
  }, [ocean, working]);
  useEffect(() => {
    if (pulse !== first.current.pulse) ocean.pulse();
  }, [ocean, pulse]);
  useEffect(() => {
    if (dim !== first.current.dim) ocean.dim();
  }, [ocean, dim]);
  useEffect(() => {
    ocean.setFacing(facing);
  }, [ocean, facing]);
  useEffect(() => {
    if (history !== first.current.history) refreshHistory();
  }, [refreshHistory, history]);
  return null;
}
