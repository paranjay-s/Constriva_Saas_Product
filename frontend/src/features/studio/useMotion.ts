/**
 * Pause motion: remembered per browser; people who ask their system for reduced motion
 * start paused. Sets html[data-motion] so CSS animations can pause too.
 */
import { useCallback, useEffect, useState } from 'react';

const KEY = 'constriva:motion';

function initial(): boolean {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved != null) return saved === 'on';
  } catch {
    // storage blocked: fall back to the system setting
  }
  return !(typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches);
}

export function useMotion(): [boolean, () => void] {
  const [on, setOn] = useState(initial);
  useEffect(() => {
    document.documentElement.dataset.motion = on ? 'on' : 'off';
  }, [on]);
  const toggle = useCallback(() => {
    setOn((v) => {
      try {
        localStorage.setItem(KEY, v ? 'off' : 'on');
      } catch {
        // not remembered; still applies now
      }
      return !v;
    });
  }, []);
  return [on, toggle];
}
