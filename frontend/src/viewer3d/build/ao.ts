// build/ao.ts
import * as THREE from 'three';
import type { MaterialLibrary } from '../materials/materials';
import type { Plan } from '../types';
import { distance } from '../utils/geometry';

/**
 * Creates a soft contact shadow plane under a piece of furniture
 */
export function createContactBlob(
  width: number,
  depth: number,
  mats: MaterialLibrary,
  y = 0.004
): THREE.Mesh {
  const w = width * 1.25;
  const d = depth * 1.25;
  const geo = new THREE.PlaneGeometry(w, d);
  geo.rotateX(-Math.PI / 2);

  const mesh = new THREE.Mesh(geo, mats.contactBlob);
  mesh.position.set(0, y, 0);
  mesh.renderOrder = 2;
  mesh.receiveShadow = false;
  mesh.castShadow = false;
  return mesh;
}

/**
 * Creates the linear gradient texture for wall base ambient occlusion
 */
function makeWallAoTexture(): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = 64;
  canvas.height = 64;
  const ctx = canvas.getContext('2d');

  if (ctx) {
    const grad = ctx.createLinearGradient(0, 0, 64, 0);
    grad.addColorStop(0, 'rgba(0, 0, 0, 0)');
    grad.addColorStop(0.25, 'rgba(0, 0, 0, 0.18)');
    grad.addColorStop(0.5, 'rgba(0, 0, 0, 0.24)');
    grad.addColorStop(0.75, 'rgba(0, 0, 0, 0.18)');
    grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 64, 64);
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

let cachedWallAoMat: THREE.MeshBasicMaterial | null = null;

export function getWallAoMaterial(): THREE.MeshBasicMaterial {
  if (!cachedWallAoMat) {
    const tex = makeWallAoTexture();
    cachedWallAoMat = new THREE.MeshBasicMaterial({
      map: tex,
      transparent: true,
      opacity: 0.6,
      depthWrite: false,
      toneMapped: false,
    });
  }
  return cachedWallAoMat;
}

/**
 * Builds soft ambient occlusion strips along the base of all walls
 */
export function buildWallBaseAO(plan: Plan): THREE.Group {
  const group = new THREE.Group();
  group.name = 'WallBaseAOGroup';
  const mat = getWallAoMaterial();

  for (const w of plan.walls) {
    const len = distance(w.a, w.b);
    if (len < 0.1) continue;

    const t = w.thickness;
    const aoWidth = t + 0.3; // 0.15m gradient strip on both sides
    const geo = new THREE.PlaneGeometry(aoWidth, len);
    geo.rotateX(-Math.PI / 2);

    const mesh = new THREE.Mesh(geo, mat);
    mesh.name = `WallAO_${w.id}`;
    mesh.renderOrder = 1;
    mesh.receiveShadow = false;
    mesh.castShadow = false;

    // Midpoint of wall
    const midX = (w.a.x + w.b.x) / 2;
    const midZ = (w.a.y + w.b.y) / 2;
    mesh.position.set(midX, 0.003, midZ);

    // Wall angle: Plane length is along Z, so rotate by wall angle
    const angle = Math.atan2(w.b.y - w.a.y, w.b.x - w.a.x);
    mesh.rotation.y = -angle + Math.PI / 2;

    group.add(mesh);
  }

  return group;
}

