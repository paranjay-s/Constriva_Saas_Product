// core/camera.ts
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type { ViewMode } from '../types';

export interface CameraContext {
  camera: THREE.PerspectiveCamera;
  controls: OrbitControls;
  fitToRadius: (radius: number, center?: THREE.Vector3) => void;
  setView: (view: ViewMode, animate?: boolean) => void;
  update: () => boolean; // returns true if actively animating
  dispose: () => void;
}

export function createCamera(
  container: HTMLElement,
  onChange: () => void
): CameraContext {
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 200);

  const controls = new OrbitControls(camera, container);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.maxPolarAngle = 1.35; // Prevents camera dipping below ground
  controls.minPolarAngle = 0.05;
  controls.screenSpacePanning = true;

  controls.addEventListener('change', onChange);

  let buildingRadius = 10;
  const buildingCenter = new THREE.Vector3(0, 0, 0);

  // Animation state
  let isAnimating = false;
  let animStart = 0;
  const animDuration = 400; // 400 ms
  const startPos = new THREE.Vector3();
  const targetPos = new THREE.Vector3();
  const startTarget = new THREE.Vector3();
  const targetLook = new THREE.Vector3();

  const fitToRadius = (radius: number, center: THREE.Vector3 = new THREE.Vector3(0, 0, 0)) => {
    buildingRadius = Math.max(radius, 2);
    buildingCenter.copy(center);

    controls.target.copy(buildingCenter);
    controls.minDistance = buildingRadius * 0.7;
    controls.maxDistance = buildingRadius * 4.5;

    setView('iso', false);
  };

  const getTargetPositionForView = (view: ViewMode): THREE.Vector3 => {
    const fovRad = THREE.MathUtils.degToRad(camera.fov);
    const dist = (buildingRadius / Math.sin(fovRad / 2)) * 1.05;

    if (view === 'top') {
      // Top down view: elevation 89°, azimuth 0°
      const elevation = THREE.MathUtils.degToRad(89);
      const azimuth = 0;
      const x = dist * Math.cos(elevation) * Math.sin(azimuth);
      const y = dist * Math.sin(elevation);
      const z = dist * Math.cos(elevation) * Math.cos(azimuth);
      return new THREE.Vector3(buildingCenter.x + x, buildingCenter.y + y, buildingCenter.z + z);
    }

    // Isometric dollhouse view: azimuth 40°, elevation 50°
    const elevation = THREE.MathUtils.degToRad(50);
    const azimuth = THREE.MathUtils.degToRad(40);
    const x = dist * Math.cos(elevation) * Math.sin(azimuth);
    const y = dist * Math.sin(elevation);
    const z = dist * Math.cos(elevation) * Math.cos(azimuth);
    return new THREE.Vector3(buildingCenter.x + x, buildingCenter.y + y, buildingCenter.z + z);
  };

  const setView = (view: ViewMode, animate: boolean = true) => {
    const pos = getTargetPositionForView(view);

    if (!animate) {
      camera.position.copy(pos);
      controls.target.copy(buildingCenter);
      controls.update();
      onChange();
      return;
    }

    isAnimating = true;
    animStart = performance.now();
    startPos.copy(camera.position);
    targetPos.copy(pos);
    startTarget.copy(controls.target);
    targetLook.copy(buildingCenter);
    onChange();
  };

  const update = (): boolean => {
    controls.update();

    if (!isAnimating) return false;

    const now = performance.now();
    const elapsed = now - animStart;
    const progress = Math.min(1.0, elapsed / animDuration);

    // Cubic ease-out
    const t = 1 - Math.pow(1 - progress, 3);

    camera.position.lerpVectors(startPos, targetPos, t);
    controls.target.lerpVectors(startTarget, targetLook, t);

    if (progress >= 1.0) {
      isAnimating = false;
    }

    return isAnimating;
  };

  return {
    camera,
    controls,
    fitToRadius,
    setView,
    update,
    dispose: () => {
      controls.removeEventListener('change', onChange);
      controls.dispose();
    },
  };
}

