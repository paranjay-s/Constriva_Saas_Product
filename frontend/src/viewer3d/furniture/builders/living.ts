// furniture/builders/living.ts
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import type { MaterialLibrary } from '../../materials/materials';
import { createContactBlob } from '../../build/ao';
import type { FurnitureMeshResult } from './bed';

/**
 * Builds 3-seater sofa with rounded cushions and a teal accent cushion
 * Dimensions: 2.1m w x 0.9m d x 0.82m h
 * Footprint origin at (0, 0, 0), front faces +Z
 */
export function buildSofa3(mats: MaterialLibrary): FurnitureMeshResult {
  const group = new THREE.Group();
  group.name = 'Sofa3';
  const w = 2.1;
  const d = 0.9;

  group.add(createContactBlob(w, d, mats));

  // Low sofa plinth base
  const plinthGeo = new THREE.BoxGeometry(w - 0.1, 0.12, d - 0.1);
  const plinth = new THREE.Mesh(plinthGeo, mats.woodFurniture);
  plinth.position.set(0, 0.06, 0);
  plinth.castShadow = true;
  group.add(plinth);

  // Main sofa backrest
  const backGeo = new RoundedBoxGeometry(w, 0.68, 0.22, 4, 0.04);
  const back = new THREE.Mesh(backGeo, mats.fabricLight);
  back.position.set(0, 0.46, -d / 2 + 0.11);
  back.castShadow = true;
  back.receiveShadow = true;
  group.add(back);

  // Armrests (left and right)
  const armGeo = new RoundedBoxGeometry(0.18, 0.56, d, 4, 0.04);
  const leftArm = new THREE.Mesh(armGeo, mats.fabricLight);
  leftArm.position.set(-w / 2 + 0.09, 0.4, 0);
  leftArm.castShadow = true;
  group.add(leftArm);

  const rightArm = new THREE.Mesh(armGeo, mats.fabricLight);
  rightArm.position.set(w / 2 - 0.09, 0.4, 0);
  rightArm.castShadow = true;
  group.add(rightArm);

  // 3 Soft Seat Cushions
  const cushionW = (w - 0.38) / 3;
  const seatD = d - 0.24;
  for (let i = 0; i < 3; i++) {
    const seatGeo = new RoundedBoxGeometry(cushionW - 0.03, 0.18, seatD, 4, 0.04);
    const seat = new THREE.Mesh(seatGeo, mats.fabricLight);
    const cx = -w / 2 + 0.19 + cushionW * i + cushionW / 2;
    seat.position.set(cx, 0.25, 0.06);
    seat.castShadow = true;
    seat.receiveShadow = true;
    group.add(seat);

    // Back cushion
    const backCushionGeo = new RoundedBoxGeometry(cushionW - 0.03, 0.36, 0.16, 4, 0.03);
    const backCushion = new THREE.Mesh(backCushionGeo, mats.fabricLight);
    backCushion.position.set(cx, 0.52, -d / 2 + 0.24);
    backCushion.rotation.x = -0.1;
    backCushion.castShadow = true;
    group.add(backCushion);
  }

  // Accent throw cushion in teal
  const accentGeo = new RoundedBoxGeometry(0.38, 0.38, 0.12, 4, 0.03);
  const accent = new THREE.Mesh(accentGeo, mats.accentTeal);
  accent.position.set(-w / 2 + 0.28, 0.42, 0.08);
  accent.rotation.y = 0.3;
  accent.rotation.z = 0.15;
  accent.castShadow = true;
  group.add(accent);

  return { group, footprint: { w, d } };
}

/**
 * Builds L-shaped sectional sofa (2.6m w x 1.6m d x 0.82m h)
 */
export function buildSofaL(mats: MaterialLibrary): FurnitureMeshResult {
  const group = new THREE.Group();
  group.name = 'SofaL';
  const w = 2.6;
  const d = 1.6;

  group.add(createContactBlob(w, d, mats));

  // Main 3-seat section (facing +Z)
  const sofaMain = buildSofa3(mats);
  sofaMain.group.position.set(-0.25, 0, -0.35);
  group.add(sofaMain.group);

  // Chaise section on the right side extending forward
  const chaiseGeo = new RoundedBoxGeometry(0.85, 0.38, 1.1, 4, 0.04);
  const chaise = new THREE.Mesh(chaiseGeo, mats.fabricLight);
  chaise.position.set(w / 2 - 0.45, 0.25, 0.4);
  chaise.castShadow = true;
  chaise.receiveShadow = true;
  group.add(chaise);

  return { group, footprint: { w, d } };
}

/**
 * Builds single armchair (0.85m w x 0.85m d x 0.8m h)
 */
export function buildArmchair(mats: MaterialLibrary): FurnitureMeshResult {
  const group = new THREE.Group();
  group.name = 'Armchair';
  const w = 0.85;
  const d = 0.85;

  group.add(createContactBlob(w, d, mats));

  // Backrest
  const backGeo = new RoundedBoxGeometry(w, 0.65, 0.18, 4, 0.04);
  const back = new THREE.Mesh(backGeo, mats.fabricLight);
  back.position.set(0, 0.45, -d / 2 + 0.09);
  back.castShadow = true;
  group.add(back);

  // Armrests
  const armGeo = new RoundedBoxGeometry(0.16, 0.52, d, 4, 0.04);
  const leftArm = new THREE.Mesh(armGeo, mats.fabricLight);
  leftArm.position.set(-w / 2 + 0.08, 0.36, 0);
  leftArm.castShadow = true;
  group.add(leftArm);

  const rightArm = new THREE.Mesh(armGeo, mats.fabricLight);
  rightArm.position.set(w / 2 - 0.08, 0.36, 0);
  rightArm.castShadow = true;
  group.add(rightArm);

  // Seat
  const seatGeo = new RoundedBoxGeometry(w - 0.34, 0.2, d - 0.2, 4, 0.04);
  const seat = new THREE.Mesh(seatGeo, mats.fabricLight);
  seat.position.set(0, 0.24, 0.05);
  seat.castShadow = true;
  group.add(seat);

  return { group, footprint: { w, d } };
}

/**
 * Builds coffee table (1.0m w x 0.6m d x 0.4m h)
 */
export function buildCoffeeTable(mats: MaterialLibrary): FurnitureMeshResult {
  const group = new THREE.Group();
  group.name = 'CoffeeTable';
  const w = 1.0;
  const d = 0.6;
  const h = 0.4;

  group.add(createContactBlob(w, d, mats));

  // Soft wood top
  const topGeo = new RoundedBoxGeometry(w, 0.04, d, 3, 0.015);
  const top = new THREE.Mesh(topGeo, mats.woodFurniture);
  top.position.set(0, h - 0.02, 0);
  top.castShadow = true;
  top.receiveShadow = true;
  group.add(top);

  // 4 slim dark legs
  const legGeo = new THREE.CylinderGeometry(0.02, 0.015, h - 0.04, 8);
  const lx = w / 2 - 0.08;
  const lz = d / 2 - 0.08;
  const legY = (h - 0.04) / 2;

  for (const [x, z] of [
    [-lx, -lz],
    [lx, -lz],
    [-lx, lz],
    [lx, lz],
  ]) {
    const leg = new THREE.Mesh(legGeo, mats.stoolDark);
    leg.position.set(x, legY, z);
    leg.castShadow = true;
    group.add(leg);
  }

  return { group, footprint: { w, d } };
}

/**
 * Builds TV console with widescreen display (1.6m w x 0.4m d x 1.25m h)
 */
export function buildTvUnit(mats: MaterialLibrary): FurnitureMeshResult {
  const group = new THREE.Group();
  group.name = 'TvUnit';
  const w = 1.6;
  const d = 0.4;

  group.add(createContactBlob(w, d, mats));

  // Low media credenza
  const credGeo = new RoundedBoxGeometry(w, 0.42, d, 3, 0.02);
  const cred = new THREE.Mesh(credGeo, mats.woodFurniture);
  cred.position.set(0, 0.21, 0);
  cred.castShadow = true;
  cred.receiveShadow = true;
  group.add(cred);

  // TV Screen base / stand
  const standGeo = new THREE.BoxGeometry(0.4, 0.03, 0.22);
  const stand = new THREE.Mesh(standGeo, mats.stoolDark);
  stand.position.set(0, 0.435, 0);
  group.add(stand);

  // TV Screen panel
  const tvGeo = new RoundedBoxGeometry(1.3, 0.75, 0.04, 2, 0.01);
  const tv = new THREE.Mesh(tvGeo, mats.stoolDark);
  tv.position.set(0, 0.85, 0);
  tv.castShadow = true;
  group.add(tv);

  return { group, footprint: { w, d } };
}

/**
 * Builds living room rug with rounded corners (2.4m w x 1.7m d)
 */
export function buildLivingRug(
  mats: MaterialLibrary,
  w = 2.4,
  d = 1.7
): FurnitureMeshResult {
  const group = new THREE.Group();
  group.name = 'LivingRug';

  const rugGeo = new RoundedBoxGeometry(w, 0.012, d, 2, 0.02);
  const rugMat = new THREE.MeshStandardMaterial({
    color: 0xd9d6cf,
    roughness: 0.95,
  });
  const rug = new THREE.Mesh(rugGeo, rugMat);
  rug.position.set(0, 0.007, 0);
  rug.receiveShadow = true;
  group.add(rug);

  // Subtle accent stripe
  const stripeGeo = new THREE.BoxGeometry(w * 0.85, 0.014, 0.08);
  const stripe = new THREE.Mesh(stripeGeo, mats.accentTeal);
  stripe.position.set(0, 0.008, d * 0.3);
  stripe.receiveShadow = true;
  group.add(stripe);

  return { group, footprint: { w, d } };
}
