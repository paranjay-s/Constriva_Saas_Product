// core/loop.ts

export interface RenderLoop {
  requestRender: () => void;
  startContinuous: (durationMs?: number) => void;
  stop: () => void;
  dispose: () => void;
}

export function createRenderLoop(renderFn: () => boolean): RenderLoop {
  let isRunning = false;
  let rafId: number | null = null;
  let continuousUntil = 0;

  const tick = () => {
    rafId = null;

    // renderFn returns true if actively animating (e.g. camera tween or cutaway lerp)
    const isAnimating = renderFn();

    const now = performance.now();
    const needsContinuous = now < continuousUntil || isAnimating;

    if (needsContinuous) {
      rafId = requestAnimationFrame(tick);
    } else {
      isRunning = false;
    }
  };

  const requestRender = () => {
    if (!isRunning) {
      isRunning = true;
      rafId = requestAnimationFrame(tick);
    }
  };

  const startContinuous = (durationMs: number = 600) => {
    continuousUntil = Math.max(continuousUntil, performance.now() + durationMs);
    requestRender();
  };

  const stop = () => {
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
    isRunning = false;
    continuousUntil = 0;
  };

  return {
    requestRender,
    startContinuous,
    stop,
    dispose: () => {
      stop();
    },
  };
}

