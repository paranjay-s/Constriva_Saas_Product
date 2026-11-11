// build/plinth.ts
import * as THREE from 'three';
import type { Plan } from '../types';
import type { MaterialLibrary } from '../materials/materials';
import { polygonBounds } from '../utils/geometry';

export interface PlinthResult {
  group: THREE.Group;
  plinthMesh: THREE.Mesh;
  groundMesh: THREE.Mesh;
  radius: number;
  center: THREE.Vector3;
}

export function buildPlinth(plan: Plan, mats: MaterialLibrary): PlinthResult {
  const group = new THREE.Group();
  group.name = 'PlinthAndGround';

  // Calculate building footprint bounding box
  let minX = Infinity;
  let maxX = -Infinity;
  let minZ = Infinity;
  let maxZ = -Infinity;

  for (const r of plan.rooms) {
    const b = polygonBounds(r.polygon);
    if (b.minX < minX) minX = b.minX;
    if (b.maxX > maxX) maxX = b.maxX;
    if (b.minY < minZ) minZ = b.minY;
    if (b.maxY > maxZ) maxZ = b.maxY;
  }

  for (const w of plan.walls) {
    minX = Math.min(minX, w.a.x, w.b.x);
    maxX = Math.max(maxX, w.a.x, w.b.x);
    minZ = Math.min(minZ, w.a.y, w.b.y);
    maxZ = Math.max(maxZ, w.a.y, w.b.y);
  }

  if (minX === Infinity) {
    minX = -5;
    maxX = 5;
    minZ = -5;
    maxZ = 5;
  }

  const cx = (minX + maxX) / 2;
  const cz = (minZ + maxZ) / 2;
  const w = maxX - minX;
  const d = maxZ - minZ;
  const radius = Math.max(Math.hypot(w / 2, d / 2), 4);
  const center = new THREE.Vector3(cx, 0, cz);

  // 1. Plinth Slab: 0.2m thick under the house, top at y = 0
  const plinthW = w + 0.3; // offset by 0.15m on all sides
  const plinthD = d + 0.3;
  const plinthH = 0.2;

  const plinthGeo = new THREE.BoxGeometry(plinthW, plinthH, plinthD);
  const plinthMesh = new THREE.Mesh(plinthGeo, mats.plinth);
  plinthMesh.name = 'PlinthSlab';
  // Center plinth so top is at y = 0
  plinthMesh.position.set(cx, -plinthH / 2, cz);
  plinthMesh.receiveShadow = true;
  plinthMesh.castShadow = true;
  group.add(plinthMesh);

  // 2. Plinth soft contact shadow on ground
  const plinthShadowGeo = new THREE.PlaneGeometry(plinthW + 1.2, plinthD + 1.2);
  plinthShadowGeo.rotateX(-Math.PI / 2);
  const plinthShadow = new THREE.Mesh(plinthShadowGeo, mats.contactBlob);
  plinthShadow.position.set(cx, -plinthH - 0.001, cz);
  group.add(plinthShadow);

  // 3. Ground Disc: large disc at y = -0.2 (below plinth)
  const groundRadius = Math.max(radius * 3.2, 35);
  const groundGeo = new THREE.CircleGeometry(groundRadius, 64);
  groundGeo.rotateX(-Math.PI / 2);
  const groundMesh = new THREE.Mesh(groundGeo, mats.ground);
  groundMesh.name = 'GroundDisc';
  groundMesh.position.set(cx, -plinthH - 0.002, cz);
  groundMesh.receiveShadow = true;
  group.add(groundMesh);

  return {
    group,
    plinthMesh,
    groundMesh,
    radius,
    center,
  };
}

