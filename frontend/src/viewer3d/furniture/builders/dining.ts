// furniture/builders/dining.ts
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import type { MaterialLibrary } from '../../materials/materials';
import { createContactBlob } from '../../build/ao';
import type { FurnitureMeshResult } from './bed';

/**
 * Builds dining chair (0.45m w x 0.45m d x 0.85m h)
 */
function buildChair(mats: MaterialLibrary): THREE.Group {
  const chair = new THREE.Group();
  chair.name = 'DiningChair';

  // Seat cushion
  const seatGeo = new RoundedBoxGeometry(0.44, 0.06, 0.42, 3, 0.02);
  const seat = new THREE.Mesh(seatGeo, mats.fabricLight);
  seat.position.set(0, 0.45, 0);
  seat.castShadow = true;
  seat.receiveShadow = true;
  chair.add(seat);

  // Backrest
  const backGeo = new RoundedBoxGeometry(0.42, 0.38, 0.04, 3, 0.015);
  const back = new THREE.Mesh(backGeo, mats.woodFurniture);
  back.position.set(0, 0.67, -0.19);
  back.castShadow = true;
  chair.add(back);

  // 4 Legs
  const legGeo = new THREE.CylinderGeometry(0.015, 0.012, 0.43, 8);
  for (const [x, z] of [
    [-0.18, -0.18],
    [0.18, -0.18],
    [-0.18, 0.18],
    [0.18, 0.18],
  ]) {
    const leg = new THREE.Mesh(legGeo, mats.woodFurniture);
    leg.position.set(x, 0.215, z);
    leg.castShadow = true;
    chair.add(leg);
  }

  return chair;
}

/**
 * Builds dining table set with 6 chairs neatly tucked in
 * Dimensions: 1.6m w x 0.9m d x 0.75m h
 */
export function buildDiningTable(mats: MaterialLibrary): FurnitureMeshResult {
  const group = new THREE.Group();
  group.name = 'DiningTableSet';
  const w = 1.6;
  const d = 0.9;
  const h = 0.75;

  // Contact shadow under the entire set
  group.add(createContactBlob(w + 0.4, d + 0.5, mats));

  // Table top
  const topGeo = new RoundedBoxGeometry(w, 0.045, d, 3, 0.015);
  const top = new THREE.Mesh(topGeo, mats.woodFurniture);
  top.position.set(0, h - 0.022, 0);
  top.castShadow = true;
  top.receiveShadow = true;
  group.add(top);

  // 4 Table Legs
  const legGeo = new THREE.CylinderGeometry(0.035, 0.025, h - 0.045, 8);
  const lx = w / 2 - 0.1;
  const lz = d / 2 - 0.1;
  const legY = (h - 0.045) / 2;

  for (const [x, z] of [
    [-lx, -lz],
    [lx, -lz],
    [-lx, lz],
    [lx, lz],
  ]) {
    const leg = new THREE.Mesh(legGeo, mats.woodFurniture);
    leg.position.set(x, legY, z);
    leg.castShadow = true;
    group.add(leg);
  }

  // 6 Chairs: 3 along front side (+Z), 3 along back side (-Z), pushed in
  const chairOffsetZ = d / 2 + 0.18; // pushed in towards table
  const chairXs = [-0.5, 0, 0.5];

  for (const cx of chairXs) {
    // Back row (facing +Z into table)
    const backChair = buildChair(mats);
    backChair.position.set(cx, 0, -chairOffsetZ);
    backChair.rotation.y = 0;
    group.add(backChair);

    // Front row (facing -Z into table)
    const frontChair = buildChair(mats);
    frontChair.position.set(cx, 0, chairOffsetZ);
    frontChair.rotation.y = Math.PI;
    group.add(frontChair);
  }

  return { group, footprint: { w: w + 0.5, d: d + 0.6 } };
}

