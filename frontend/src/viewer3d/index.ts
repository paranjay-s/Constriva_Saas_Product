// index.ts — Core vanilla Three.js Dollhouse Viewer
import * as THREE from 'three';
import type { Plan, ViewMode, ViewerApi, ViewerOptions, WallMode } from './types';
import { createRenderer } from './core/renderer';
import { createCamera, type CameraContext } from './core/camera';
import { createLights } from './core/lights';
import { setupEnvironment } from './core/environment';
import { createRenderLoop, type RenderLoop } from './core/loop';
import { getOrCreateMaterials, type MaterialLibrary } from './materials/materials';
import { PALETTE } from './materials/palette';
import { buildPlinth } from './build/plinth';
import { buildFloors, type FloorsResult } from './build/floors';
import { buildWalls, type WallsResult } from './build/walls';
import { buildWallBaseAO } from './build/ao';
import { stagePlan } from './furniture/stage';
import { CutawayController } from './ui/cutaway';
import { LabelOverlay } from './ui/labels';
import { deepDispose } from './utils/dispose';

export * from './types';
export { normalizePlan } from './adapter/normalizePlan';

export function createViewer(
  container: HTMLElement,
  opts?: ViewerOptions
): ViewerApi {
  // Check WebGL availability
  try {
    const canvas = document.createElement('canvas');
    const gl =
      canvas.getContext('webgl2') || canvas.getContext('webgl');
    if (!gl) {
      throw new Error('WebGL not supported');
    }
  } catch {
    container.innerHTML = `
      <div style="display: flex; height: 100%; align-items: center; justify-content: center; background: #FAF8F4; color: #4B5563; font-family: sans-serif; text-align: center; padding: 20px;">
        <div>
          <p style="font-size: 16px; font-weight: 600; margin-bottom: 8px;">3D Acceleration Unavailable</p>
          <p style="font-size: 13px; color: #6B7280;">Please enable hardware acceleration in your browser settings to view the 3D floor plan.</p>
        </div>
      </div>
    `;
    return {
      loadPlan: () => {},
      setView: () => {},
      setFurniture: () => {},
      setLabels: () => {},
      setWallMode: () => {},
      setMaterialHighlight: () => {},
      selectRoom: () => {},
      screenshot: () => '',
      dispose: () => {},
    };
  }

  // Stylish warm background radial gradient as per tokens
  container.style.background = `radial-gradient(ellipse at 50% 40%, ${PALETTE.bgTop}, ${PALETTE.bgBottom})`;
  container.style.position = 'relative';

  const scene = new THREE.Scene();
  scene.name = 'DollhouseScene';

  let currentWallMode: WallMode = opts?.initialWallMode ?? 'auto';
  let showFurniture = opts?.showFurniture ?? true;
  let showLabels = opts?.showLabels ?? false;

  let furnitureGroup: THREE.Group | null = null;
  let wallsResult: WallsResult | null = null;
  let floorsResult: FloorsResult | null = null;
  let cutawayController: CutawayController | null = null;
  let labelOverlay: LabelOverlay | null = null;

  let loop: RenderLoop;
  let requestRender = () => {};
  let cameraContext: CameraContext;

  const rendererInstance = createRenderer(container, (w, h) => {
    if (cameraContext) {
      cameraContext.camera.aspect = w / h;
      cameraContext.camera.updateProjectionMatrix();
    }
    requestRender();
  });
  const { renderer, dispose: disposeRenderer } = rendererInstance;

  cameraContext = createCamera(container, () => {
    if (cutawayController && currentWallMode === 'auto') {
      cutawayController.evaluateTargets();
      loop?.startContinuous(600);
    }
    if (labelOverlay && showLabels) {
      labelOverlay.update();
    }
    requestRender();
  });

  const lightsContext = createLights();
  scene.add(lightsContext.group);

  const envSystem = setupEnvironment(renderer, scene);
  const maxAnisotropy = renderer.capabilities.getMaxAnisotropy();
  const mats: MaterialLibrary = getOrCreateMaterials(maxAnisotropy);

  const modelGroup = new THREE.Group();
  modelGroup.name = 'ModelGroup';
  scene.add(modelGroup);

  const onRender = (): boolean => {
    const camMoving = cameraContext.update();
    let cutawayMoving = false;
    if (cutawayController) {
      cutawayMoving = cutawayController.update();
    }

    if (labelOverlay && showLabels) {
      labelOverlay.update();
    }

    renderer.render(scene, cameraContext.camera);
    return camMoving || cutawayMoving;
  };

  loop = createRenderLoop(onRender);
  requestRender = loop.requestRender;

  const loadPlan = (plan: Plan) => {
    // Dispose old meshes and labels
    deepDispose(modelGroup);
    while (modelGroup.children.length > 0) {
      modelGroup.remove(modelGroup.children[0]);
    }
    if (labelOverlay) {
      labelOverlay.dispose();
      labelOverlay = null;
    }

    // 1. Build Plinth and Ground Disc
    const plinthRes = buildPlinth(plan, mats);
    modelGroup.add(plinthRes.group);

    // 2. Build Floors with continuous world-UV texture alignment
    floorsResult = buildFloors(plan, mats);
    modelGroup.add(floorsResult.group);

    // 3. Build Soft Wall Base AO
    const aoGroup = buildWallBaseAO(plan);
    modelGroup.add(aoGroup);

    // 4. Build Walls with dark exterior caps and openings
    wallsResult = buildWalls(plan, mats, plinthRes.center);
    modelGroup.add(wallsResult.group);

    // 5. Build Furniture Layer
    furnitureGroup = stagePlan(plan, mats);
    furnitureGroup.visible = showFurniture;
    modelGroup.add(furnitureGroup);

    // 6. Setup Cutaway Controller for exterior walls
    cutawayController = new CutawayController(
      wallsResult.exteriorWalls,
      plinthRes.center,
      cameraContext.camera,
      requestRender,
      currentWallMode
    );

    // 7. Setup 2D Projected Centroid Labels
    labelOverlay = new LabelOverlay(
      container,
      plan,
      cameraContext.camera,
      showLabels
    );

    // 8. Align directional sun shadow camera to building bounds
    lightsContext.updateBounds(plinthRes.radius, plinthRes.center);

    // 9. Smoothly position camera to frame the building
    cameraContext.fitToRadius(plinthRes.radius, plinthRes.center);
    cameraContext.setView(opts?.initialView || 'iso', false);

    // Trigger initial render
    requestRender();
  };

  const setView = (v: ViewMode) => {
    cameraContext.setView(v, true);
    loop.startContinuous(600);
    opts?.onViewChange?.(v);
  };

  const setFurniture = (on: boolean) => {
    showFurniture = on;
    if (furnitureGroup) {
      furnitureGroup.visible = on;
      requestRender();
    }
  };

  const setLabels = (on: boolean) => {
    showLabels = on;
    if (labelOverlay) {
      labelOverlay.setVisible(on);
      requestRender();
    }
  };

  const setWallMode = (m: WallMode) => {
    currentWallMode = m;
    if (cutawayController) {
      cutawayController.setMode(m);
      loop.startContinuous(600);
    }
  };

  const setMaterialHighlight = (tag: string | null) => {
    if (wallsResult) wallsResult.updateHighlight(tag);
    if (floorsResult) floorsResult.updateHighlight(tag);
    requestRender();
  };

  const selectRoom = (roomId: string | null) => {
    if (floorsResult) {
      floorsResult.selectRoom(roomId);
      requestRender();
    }
  };

  const screenshot = (): string => {
    renderer.render(scene, cameraContext.camera);
    return renderer.domElement.toDataURL('image/png');
  };

  const dispose = () => {
    loop.dispose();
    cameraContext.dispose();
    lightsContext.dispose();
    if (labelOverlay) labelOverlay.dispose();
    deepDispose(modelGroup);
    envSystem.dispose();
    mats.dispose();
    disposeRenderer();
  };

  return {
    loadPlan,
    setView,
    setFurniture,
    setLabels,
    setWallMode,
    setMaterialHighlight,
    selectRoom,
    screenshot,
    dispose,
  };
}
