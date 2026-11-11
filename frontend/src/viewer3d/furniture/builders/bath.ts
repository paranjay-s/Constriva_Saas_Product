// furniture/builders/bath.ts
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import type { MaterialLibrary } from '../../materials/materials';
import { createContactBlob } from '../../build/ao';
import type { FurnitureMeshResult } from './bed';

/**
 * Builds water closet (toilet) from soft rounded boxes
 * Dimensions: 0.4m w x 0.65m d x 0.78m h
 * Footprint origin at (0, 0, 0), front faces +Z (tank at -Z against wall)
 */
export function buildWc(mats: MaterialLibrary): FurnitureMeshResult {
  const group = new THREE.Group();
  group.name = 'WaterCloset';
  const w = 0.4;
  const d = 0.65;

  group.add(createContactBlob(w, d, mats));

  // Ceramic material
  const ceramicMat = mats.stone;

  // Rear cistern tank
  const tankGeo = new RoundedBoxGeometry(0.38, 0.45, 0.22, 3, 0.02);
  const tank = new THREE.Mesh(tankGeo, ceramicMat);
  tank.position.set(0, 0.55, -d / 2 + 0.11);
  tank.castShadow = true;
  group.add(tank);

  // Toilet bowl
  const bowlGeo = new RoundedBoxGeometry(0.36, 0.38, 0.42, 4, 0.04);
  const bowl = new THREE.Mesh(bowlGeo, ceramicMat);
  bowl.position.set(0, 0.19, 0.08);
  bowl.castShadow = true;
  group.add(bowl);

  // Seat lid
  const lidGeo = new RoundedBoxGeometry(0.34, 0.03, 0.4, 3, 0.015);
  const lid = new THREE.Mesh(lidGeo, mats.fabricLight);
  lid.position.set(0, 0.39, 0.08);
  group.add(lid);

  return { group, footprint: { w, d } };
}

/**
 * Builds bathroom vanity with basin and wall mirror
 * Dimensions: 0.7m w x 0.45m d x 0.85m h (mirror up to 1.8m)
 */
export function buildVanity(
  mats: MaterialLibrary,
  width = 0.7
): FurnitureMeshResult {
  const group = new THREE.Group();
  group.name = 'Vanity';
  const w = width;
  const d = 0.45;
  const h = 0.85;

  group.add(createContactBlob(w, d, mats));

  // Wood vanity vanity unit
  const unitGeo = new RoundedBoxGeometry(w, h - 0.04, d, 3, 0.02);
  const unit = new THREE.Mesh(unitGeo, mats.woodFurniture);
  unit.position.set(0, (h - 0.04) / 2, 0);
  unit.castShadow = true;
  unit.receiveShadow = true;
  group.add(unit);

  // Stone countertop with inset basin
  const topGeo = new RoundedBoxGeometry(w + 0.02, 0.04, d + 0.02, 2, 0.01);
  const top = new THREE.Mesh(topGeo, mats.stone);
  top.position.set(0, h - 0.02, 0);
  top.castShadow = true;
  group.add(top);

  // Ceramic basin
  const basinGeo = new RoundedBoxGeometry(0.44, 0.08, 0.32, 3, 0.02);
  const basin = new THREE.Mesh(basinGeo, mats.stone);
  basin.position.set(0, h + 0.03, 0.02);
  basin.castShadow = true;
  group.add(basin);

  // Faucet
  const faucetGeo = new THREE.CylinderGeometry(0.015, 0.015, 0.18, 8);
  const faucet = new THREE.Mesh(faucetGeo, mats.stoolDark);
  faucet.position.set(0, h + 0.09, -0.12);
  group.add(faucet);

  // Wall mirror (positioned above vanity against rear -Z wall)
  const mirrorGeo = new RoundedBoxGeometry(w - 0.1, 0.7, 0.02, 2, 0.01);
  const mirror = new THREE.Mesh(mirrorGeo, mats.glass);
  mirror.position.set(0, h + 0.5, -d / 2 + 0.01);
  group.add(mirror);

  return { group, footprint: { w, d } };
}

/**
 * Builds walk-in shower enclosure with low tray and glass partition
 * Dimensions: 0.9m w x 0.9m d x 2.0m h
 */
export function buildShower(
  mats: MaterialLibrary,
  size = 0.9
): FurnitureMeshResult {
  const group = new THREE.Group();
  group.name = 'ShowerEnclosure';
  const w = size;
  const d = size;

  // Shallow stone shower tray
  const trayGeo = new THREE.BoxGeometry(w, 0.04, d);
  const tray = new THREE.Mesh(trayGeo, mats.stone);
  tray.position.set(0, 0.02, 0);
  tray.receiveShadow = true;
  group.add(tray);

  // Glass screen panel along right edge (+X)
  const glassGeo1 = new THREE.BoxGeometry(0.015, 1.95, d);
  const screen1 = new THREE.Mesh(glassGeo1, mats.glass);
  screen1.position.set(w / 2 - 0.01, 1.0, 0);
  screen1.castShadow = false;
  group.add(screen1);

  // Dark shower riser rail & head
  const railGeo = new THREE.CylinderGeometry(0.012, 0.012, 1.8, 8);
  const rail = new THREE.Mesh(railGeo, mats.stoolDark);
  rail.position.set(-w / 2 + 0.08, 1.1, -d / 2 + 0.08);
  group.add(rail);

  const headGeo = new THREE.CylinderGeometry(0.1, 0.1, 0.02, 16);
  const head = new THREE.Mesh(headGeo, mats.stoolDark);
  head.position.set(-w / 2 + 0.18, 1.95, -d / 2 + 0.18);
  head.rotation.x = Math.PI / 2;
  group.add(head);

  return { group, footprint: { w, d } };
}

