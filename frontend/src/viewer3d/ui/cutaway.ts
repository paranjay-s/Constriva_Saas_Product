// ui/cutaway.ts
import * as THREE from 'three';
import type { ExteriorWallNode } from '../build/walls';
import type { WallMode } from '../types';

export class CutawayController {
  private mode: WallMode = 'auto';
  private exteriorWalls: ExteriorWallNode[] = [];
  private buildingCenter: THREE.Vector3;
  private camera: THREE.Camera;
  private currentScales: number[] = [];
  private targetScales: number[] = [];
  private onRequestRender: () => void;

  constructor(
    exteriorWalls: ExteriorWallNode[],
    buildingCenter: THREE.Vector3,
    camera: THREE.Camera,
    onRequestRender: () => void,
    initialMode: WallMode = 'auto'
  ) {
    this.exteriorWalls = exteriorWalls;
    this.buildingCenter = buildingCenter;
    this.camera = camera;
    this.onRequestRender = onRequestRender;
    this.mode = initialMode;

    this.currentScales = exteriorWalls.map(() => 1.0);
    this.targetScales = exteriorWalls.map(() => 1.0);
    this.evaluateTargets();
  }

  setMode(mode: WallMode) {
    if (this.mode === mode) return;
    this.mode = mode;
    this.evaluateTargets();
    this.onRequestRender();
  }

  getMode(): WallMode {
    return this.mode;
  }

  /**
   * Evaluates target heights based on current camera orientation and active mode
   */
  evaluateTargets() {
    const camX = this.camera.position.x - this.buildingCenter.x;
    const camZ = this.camera.position.z - this.buildingCenter.z;
    const camDist = Math.hypot(camX, camZ);
    const dirX = camDist > 1e-4 ? camX / camDist : 0;
    const dirZ = camDist > 1e-4 ? camZ / camDist : 1;

    for (let i = 0; i < this.exteriorWalls.length; i++) {
      const node = this.exteriorWalls[i];
      const lowScale = Math.max(0.2, 1.0 / node.baseHeight); // Low wall ~1.0m height

      if (this.mode === 'full') {
        this.targetScales[i] = 1.0;
      } else if (this.mode === 'low') {
        this.targetScales[i] = lowScale;
      } else {
        // Auto dollhouse cutaway: walls facing the camera drop to low height
        // normal.x is world X, normal.y is world Z
        const facing = node.normal.x * dirX + node.normal.y * dirZ;
        this.targetScales[i] = facing > 0.25 ? lowScale : 1.0;
      }
    }
  }

  /**
   * Updates scale animation smoothly with damping
   * Returns true if animation is still progressing
   */
  update(delta = 0.016): boolean {
    let isMoving = false;
    const speed = Math.min(1.0, delta * 12);

    for (let i = 0; i < this.exteriorWalls.length; i++) {
      const current = this.currentScales[i];
      const target = this.targetScales[i];
      const diff = target - current;

      if (Math.abs(diff) > 0.002) {
        const next = current + diff * speed;
        this.currentScales[i] = next;
        this.exteriorWalls[i].group.scale.y = next;
        isMoving = true;
      } else if (current !== target) {
        this.currentScales[i] = target;
        this.exteriorWalls[i].group.scale.y = target;
      }
    }

    return isMoving;
  }
}

