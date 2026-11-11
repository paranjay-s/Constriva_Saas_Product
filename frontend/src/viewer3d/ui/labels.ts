// ui/labels.ts
import * as THREE from 'three';
import type { Plan } from '../types';
import { polygonCentroid } from '../utils/geometry';
import { formatMetersToFtIn } from '../utils/units';

export interface LabelNode {
  element: HTMLDivElement;
  worldPos: THREE.Vector3;
}

export class LabelOverlay {
  private container: HTMLElement;
  private overlayDiv: HTMLDivElement;
  private labels: LabelNode[] = [];
  private isVisible = false;
  private camera: THREE.PerspectiveCamera;
  private tempVec = new THREE.Vector3();

  constructor(
    container: HTMLElement,
    plan: Plan,
    camera: THREE.PerspectiveCamera,
    initialVisible = false
  ) {
    this.container = container;
    this.camera = camera;
    this.isVisible = initialVisible;

    this.overlayDiv = document.createElement('div');
    this.overlayDiv.className = 'dollhouse-labels-overlay';
    this.overlayDiv.style.position = 'absolute';
    this.overlayDiv.style.inset = '0';
    this.overlayDiv.style.pointerEvents = 'none';
    this.overlayDiv.style.overflow = 'hidden';
    this.overlayDiv.style.display = initialVisible ? 'block' : 'none';
    this.overlayDiv.style.zIndex = '10';

    container.appendChild(this.overlayDiv);
    this.createLabels(plan);
  }

  private createLabels(plan: Plan) {
    for (const room of plan.rooms) {
      if (room.polygon.length < 3) continue;

      const centroid = polygonCentroid(room.polygon);
      const worldPos = new THREE.Vector3(centroid.x, 0.4, centroid.y);

      const pill = document.createElement('div');
      pill.className = 'room-label-pill';
      pill.style.position = 'absolute';
      pill.style.left = '0';
      pill.style.top = '0';
      pill.style.transform = 'translate(-50%, -50%)';
      pill.style.backgroundColor = 'rgba(255, 255, 255, 0.94)';
      pill.style.backdropFilter = 'blur(4px)';
      pill.style.border = '1px solid rgba(0, 0, 0, 0.08)';
      pill.style.borderRadius = '9999px';
      pill.style.boxShadow = '0 3px 10px rgba(0, 0, 0, 0.08)';
      pill.style.padding = '3px 9px';
      pill.style.display = 'flex';
      pill.style.flexDirection = 'column';
      pill.style.alignItems = 'center';
      pill.style.justifyContent = 'center';
      pill.style.whiteSpace = 'nowrap';
      pill.style.userSelect = 'none';

      // Title
      const titleSpan = document.createElement('span');
      titleSpan.style.fontSize = '11px';
      titleSpan.style.fontWeight = '600';
      titleSpan.style.color = '#1f2937';
      titleSpan.style.letterSpacing = '-0.01em';
      titleSpan.textContent = room.label || room.type.toUpperCase();
      pill.appendChild(titleSpan);

      // Dimension
      if (room.dims && (room.dims.w > 0 || room.dims.d > 0)) {
        const dimSpan = document.createElement('span');
        dimSpan.style.fontSize = '9px';
        dimSpan.style.fontWeight = '500';
        dimSpan.style.color = '#6b7280';
        dimSpan.textContent = formatMetersToFtIn(room.dims.w, room.dims.d);
        pill.appendChild(dimSpan);
      }

      this.overlayDiv.appendChild(pill);
      this.labels.push({ element: pill, worldPos });
    }
  }

  setVisible(visible: boolean) {
    this.isVisible = visible;
    this.overlayDiv.style.display = visible ? 'block' : 'none';
    if (visible) {
      this.update();
    }
  }

  getVisible(): boolean {
    return this.isVisible;
  }

  update() {
    if (!this.isVisible) return;

    const width = this.container.clientWidth;
    const height = this.container.clientHeight;
    if (width === 0 || height === 0) return;

    for (const item of this.labels) {
      this.tempVec.copy(item.worldPos);
      this.tempVec.project(this.camera);

      // Hide if behind camera
      if (this.tempVec.z > 1.0) {
        item.element.style.display = 'none';
        continue;
      }

      item.element.style.display = 'flex';
      const x = (this.tempVec.x * 0.5 + 0.5) * width;
      const y = (-this.tempVec.y * 0.5 + 0.5) * height;

      item.element.style.transform = `translate(-50%, -50%) translate3d(${Math.round(x)}px, ${Math.round(y)}px, 0)`;
    }
  }

  dispose() {
    if (this.overlayDiv && this.overlayDiv.parentNode) {
      this.overlayDiv.parentNode.removeChild(this.overlayDiv);
    }
    this.labels = [];
  }
}
