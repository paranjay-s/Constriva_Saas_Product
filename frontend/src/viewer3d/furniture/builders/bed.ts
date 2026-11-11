// furniture/builders/bed.ts
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import type { MaterialLibrary } from '../../materials/materials';
import { createContactBlob } from '../../build/ao';

export interface FurnitureMeshResult {
  group: THREE.Group;
  footprint: { w: number; d: number };
}

/**
 * Builds double bed with headboard, linen mattress, pillows, and folded teal runner
 * Dimensions: 1.6m wide, 2.05m deep, 0.95m headboard height
 * Footprint origin at (0, 0, 0), front faces +Z (headboard at -Z)
 */
export function buildDoubleBed(mats: MaterialLibrary): FurnitureMeshResult {
  const group = new THREE.Group();
  group.name = 'DoubleBed';
  const w = 1.6;
  const d = 2.05;

  // Contact shadow blob
  group.add(createContactBlob(w, d, mats));

  // Wood bed frame base
  const baseGeo = new THREE.BoxGeometry(w, 0.28, d);
  const baseMesh = new THREE.Mesh(baseGeo, mats.woodFurniture);
  baseMesh.position.set(0, 0.14, 0);
  baseMesh.castShadow = true;
  baseMesh.receiveShadow = true;
  group.add(baseMesh);

  // Soft rounded mattress
  const mattressGeo = new RoundedBoxGeometry(w - 0.06, 0.22, d - 0.08, 4, 0.04);
  const mattressMesh = new THREE.Mesh(mattressGeo, mats.linen);
  mattressMesh.position.set(0, 0.28 + 0.11, 0.02);
  mattressMesh.castShadow = true;
  mattressMesh.receiveShadow = true;
  group.add(mattressMesh);

  // Elegant Headboard at rear (-Z)
  const headboardGeo = new RoundedBoxGeometry(w + 0.06, 0.95, 0.08, 4, 0.02);
  const headboard = new THREE.Mesh(headboardGeo, mats.woodFurniture);
  headboard.position.set(0, 0.95 / 2, -d / 2 + 0.04);
  headboard.castShadow = true;
  headboard.receiveShadow = true;
  group.add(headboard);

  // Two soft linen pillows
  const pillowGeo = new RoundedBoxGeometry(0.58, 0.11, 0.38, 4, 0.03);
  const leftPillow = new THREE.Mesh(pillowGeo, mats.linen);
  leftPillow.position.set(-0.38, 0.45, -0.62);
  leftPillow.rotation.x = -0.15;
  leftPillow.castShadow = true;
  group.add(leftPillow);

  const rightPillow = new THREE.Mesh(pillowGeo, mats.linen);
  rightPillow.position.set(0.38, 0.45, -0.62);
  rightPillow.rotation.x = -0.15;
  rightPillow.castShadow = true;
  group.add(rightPillow);

  // Folded runner at bed foot in accentTeal
  const runnerGeo = new RoundedBoxGeometry(w - 0.04, 0.03, 0.45, 2, 0.015);
  const runner = new THREE.Mesh(runnerGeo, mats.accentTeal);
  runner.position.set(0, 0.505, 0.68);
  runner.castShadow = true;
  group.add(runner);

  return { group, footprint: { w, d } };
}

/**
 * Builds small bedside nightstand (0.45m w x 0.4m d x 0.5m h)
 */
export function buildNightstand(mats: MaterialLibrary): FurnitureMeshResult {
  const group = new THREE.Group();
  group.name = 'Nightstand';
  const w = 0.45;
  const d = 0.4;
  const h = 0.5;

  group.add(createContactBlob(w, d, mats));

  const bodyGeo = new RoundedBoxGeometry(w, h, d, 3, 0.02);
  const body = new THREE.Mesh(bodyGeo, mats.woodFurniture);
  body.position.set(0, h / 2, 0);
  body.castShadow = true;
  body.receiveShadow = true;
  group.add(body);

  // Small knob
  const knobGeo = new THREE.BoxGeometry(0.04, 0.02, 0.02);
  const knob = new THREE.Mesh(knobGeo, mats.stoolDark);
  knob.position.set(0, h * 0.6, d / 2 + 0.01);
  group.add(knob);

  return { group, footprint: { w, d } };
}

/**
 * Builds full-height wardrobe (1.8m w x 0.6m d x 2.1m h)
 */
export function buildWardrobe(mats: MaterialLibrary, width = 1.8): FurnitureMeshResult {
  const group = new THREE.Group();
  group.name = 'Wardrobe';
  const w = width;
  const d = 0.6;
  const h = 2.1;

  group.add(createContactBlob(w, d, mats));

  // Main cabinet
  const bodyGeo = new RoundedBoxGeometry(w, h, d, 3, 0.02);
  const body = new THREE.Mesh(bodyGeo, mats.fabricLight);
  body.position.set(0, h / 2, 0);
  body.castShadow = true;
  body.receiveShadow = true;
  group.add(body);

  // Vertical panel seams
  const numDoors = 3;
  const doorW = w / numDoors;
  for (let i = 1; i < numDoors; i++) {
    const seamGeo = new THREE.BoxGeometry(0.01, h - 0.05, 0.01);
    const seam = new THREE.Mesh(seamGeo, mats.woodFurniture);
    seam.position.set(-w / 2 + i * doorW, h / 2, d / 2 + 0.005);
    group.add(seam);
  }

  return { group, footprint: { w, d } };
}

