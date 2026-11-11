// core/renderer.ts
import * as THREE from 'three';

export interface RendererContext {
  renderer: THREE.WebGLRenderer;
  resizeObserver: ResizeObserver;
  dispose: () => void;
}

export function createRenderer(
  container: HTMLElement,
  onResize: (width: number, height: number) => void
): RendererContext {
  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: true,
    preserveDrawingBuffer: false,
    powerPreference: 'high-performance',
  });

  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  // THREE.NeutralToneMapping keeps whites bright without grey cast
  if ((THREE as any).NeutralToneMapping) {
    renderer.toneMapping = (THREE as any).NeutralToneMapping;
  } else {
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
  }
  renderer.toneMappingExposure = 1.0;

  // Soft shadows
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  // Append canvas
  container.style.position = 'relative';
  container.style.overflow = 'hidden';
  const canvas = renderer.domElement;
  canvas.style.display = 'block';
  canvas.style.width = '100%';
  canvas.style.height = '100%';
  container.appendChild(canvas);

  const updateSize = () => {
    const width = container.clientWidth || 800;
    const height = container.clientHeight || 600;
    renderer.setSize(width, height, false);
    onResize(width, height);
  };

  updateSize();

  const resizeObserver = new ResizeObserver(() => {
    updateSize();
  });
  resizeObserver.observe(container);

  return {
    renderer,
    resizeObserver,
    dispose: () => {
      resizeObserver.disconnect();
      if (canvas.parentElement) {
        canvas.parentElement.removeChild(canvas);
      }
      renderer.dispose();
      renderer.forceContextLoss();
    },
  };
}

