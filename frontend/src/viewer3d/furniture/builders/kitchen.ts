// furniture/builders/kitchen.ts
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import type { MaterialLibrary } from '../../materials/materials';
import { createContactBlob } from '../../build/ao';
import type { FurnitureMeshResult } from './bed';

/**
 * Builds kitchen counter run with base cabinets, stone countertop, gas hob, and inset sink
 * Dimensions: length (m) x 0.6m d x 0.9m h
 * Footprint origin at (0, 0, 0), front faces +Z (back against -Z wall)
 */
export function buildKitchenRun(
  mats: MaterialLibrary,
  length = 2.8
): FurnitureMeshResult {
  const group = new THREE.Group();
  group.name = 'KitchenRun';
  const w = length;
  const d = 0.6;
  const h = 0.9;

  group.add(createContactBlob(w, d, mats));

  // Lower cabinets
  const baseH = h - 0.05;
  const baseGeo = new THREE.BoxGeometry(w, baseH, d - 0.04);
  const base = new THREE.Mesh(baseGeo, mats.woodFurniture);
  base.position.set(0, baseH / 2, -0.02);
  base.castShadow = true;
  base.receiveShadow = true;
  group.add(base);

  // Stone countertop with smooth edge
  const topGeo = new RoundedBoxGeometry(w, 0.05, d, 2, 0.01);
  const top = new THREE.Mesh(topGeo, mats.stone);
  top.position.set(0, h - 0.025, 0);
  top.castShadow = true;
  top.receiveShadow = true;
  group.add(top);

  // Gas Hob cooktop (placed on left side)
  const hobX = -w / 4;
  const hobPlateGeo = new THREE.BoxGeometry(0.7, 0.015, 0.45);
  const hobPlate = new THREE.Mesh(hobPlateGeo, mats.stoolDark);
  hobPlate.position.set(hobX, h + 0.008, 0);
  group.add(hobPlate);

  // 4 burner discs
  const burnerGeo = new THREE.CylinderGeometry(0.06, 0.06, 0.01, 16);
  for (const [bx, bz] of [
    [-0.18, -0.1],
    [0.18, -0.1],
    [-0.18, 0.1],
    [0.18, 0.1],
  ]) {
    const burner = new THREE.Mesh(burnerGeo, mats.stoolDark);
    burner.position.set(hobX + bx, h + 0.02, bz);
    group.add(burner);
  }

  // Sink basin (placed on right side)
  const sinkX = w / 4;
  const sinkGeo = new THREE.BoxGeometry(0.65, 0.02, 0.42);
  const sink = new THREE.Mesh(sinkGeo, mats.stoolDark);
  sink.position.set(sinkX, h + 0.005, 0);
  group.add(sink);

  // Mixer tap faucet
  const faucetGeo = new THREE.CylinderGeometry(0.015, 0.015, 0.28, 8);
  const faucet = new THREE.Mesh(faucetGeo, mats.stoolDark);
  faucet.position.set(sinkX, h + 0.14, -0.16);
  faucet.castShadow = true;
  group.add(faucet);

  const spoutGeo = new THREE.BoxGeometry(0.02, 0.02, 0.12);
  const spout = new THREE.Mesh(spoutGeo, mats.stoolDark);
  spout.position.set(sinkX, h + 0.26, -0.1);
  group.add(spout);

  return { group, footprint: { w, d } };
}

/**
 * Builds breakfast bar kitchen island with 3 dark bar stools
 * Dimensions: 1.8m w x 0.8m d x 0.92m h
 */
export function buildKitchenIsland(
  mats: MaterialLibrary,
  w = 1.8,
  d = 0.8
): FurnitureMeshResult {
  const group = new THREE.Group();
  group.name = 'KitchenIsland';
  const h = 0.92;

  group.add(createContactBlob(w, d + 0.35, mats));

  // Island base cabinet
  const baseGeo = new THREE.BoxGeometry(w - 0.2, h - 0.06, d - 0.2);
  const base = new THREE.Mesh(baseGeo, mats.woodFurniture);
  base.position.set(0, (h - 0.06) / 2, -0.08);
  base.castShadow = true;
  base.receiveShadow = true;
  group.add(base);

  // Overhanging stone countertop
  const topGeo = new RoundedBoxGeometry(w, 0.06, d, 2, 0.01);
  const top = new THREE.Mesh(topGeo, mats.stone);
  top.position.set(0, h - 0.03, 0);
  top.castShadow = true;
  top.receiveShadow = true;
  group.add(top);

  // 3 Bar Stools along the front overhang (+Z)
  const stoolXs = [-0.5, 0, 0.5];
  const stoolZ = d / 2 + 0.22;
  const seatGeo = new THREE.CylinderGeometry(0.18, 0.18, 0.05, 16);
  const stoolLegGeo = new THREE.CylinderGeometry(0.012, 0.012, 0.65, 8);

  for (const sx of stoolXs) {
    const stool = new THREE.Group();
    stool.name = 'BarStool';

    // Seat
    const seat = new THREE.Mesh(seatGeo, mats.stoolDark);
    seat.position.set(0, 0.65, 0);
    seat.castShadow = true;
    stool.add(seat);

    // Legs
    for (const [lx, lz] of [
      [-0.1, -0.1],
      [0.1, -0.1],
      [-0.1, 0.1],
      [0.1, 0.1],
    ]) {
      const leg = new THREE.Mesh(stoolLegGeo, mats.stoolDark);
      leg.position.set(lx, 0.325, lz);
      leg.castShadow = true;
      stool.add(leg);
    }

    stool.position.set(sx, 0, stoolZ);
    group.add(stool);
  }

  return { group, footprint: { w, d: d + 0.45 } };
}

