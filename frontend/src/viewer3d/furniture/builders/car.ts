// furniture/builders/car.ts
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import type { MaterialLibrary } from '../../materials/materials';
import { createContactBlob } from '../../build/ao';
import type { FurnitureMeshResult } from './bed';

/**
 * Builds compact sedan car for parking / garage staging
 * Dimensions: 4.2m length (along Z) x 1.8m width (along X) x 1.4m height
 * Front faces +Z
 */
export function buildCar(mats: MaterialLibrary): FurnitureMeshResult {
  const group = new THREE.Group();
  group.name = 'Car';
  const w = 1.8;
  const d = 4.2;

  group.add(createContactBlob(w + 0.2, d + 0.2, mats));

  // Car lower body
  const bodyGeo = new RoundedBoxGeometry(w, 0.55, d, 4, 0.08);
  const body = new THREE.Mesh(bodyGeo, mats.car);
  body.position.set(0, 0.42, 0);
  body.castShadow = true;
  body.receiveShadow = true;
  group.add(body);

  // Cabin / Greenhouse (roof & windows)
  const cabinGeo = new RoundedBoxGeometry(w - 0.16, 0.55, d * 0.55, 4, 0.08);
  const cabin = new THREE.Mesh(cabinGeo, mats.glass);
  cabin.position.set(0, 0.88, -0.2);
  cabin.castShadow = true;
  group.add(cabin);

  // 4 Wheels / Tyres
  const tyreMat = mats.stoolDark;
  const tyreGeo = new THREE.CylinderGeometry(0.28, 0.28, 0.18, 16);
  tyreGeo.rotateZ(Math.PI / 2);

  const wheelX = w / 2 - 0.02;
  const wheelZs = [-d * 0.32, d * 0.32];

  for (const z of wheelZs) {
    // Left wheel
    const leftTyre = new THREE.Mesh(tyreGeo, tyreMat);
    leftTyre.position.set(-wheelX, 0.28, z);
    leftTyre.castShadow = true;
    group.add(leftTyre);

    // Right wheel
    const rightTyre = new THREE.Mesh(tyreGeo, tyreMat);
    rightTyre.position.set(wheelX, 0.28, z);
    rightTyre.castShadow = true;
    group.add(rightTyre);
  }

  return { group, footprint: { w, d } };
}

