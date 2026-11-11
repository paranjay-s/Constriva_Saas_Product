// frontend/src/features/plan-viewer/furniture/furnitureLibrary.tsx
// High-Detail Procedural PBR Furniture Catalog
import * as THREE from 'three';
import {
  getPbrMaterialCatalog,
  type PbrMaterialCatalog,
} from '../materials/materials';

export interface FurnitureFootprint {
  group: THREE.Group;
  width: number;
  depth: number;
}

/**
 * Builds Master King Bed with tufted headboard, folded duvet, pillows & nightstand lamps
 * Dimensions: 2.0m w x 2.15m d x 1.1m h (headboard at -Z)
 */
export function buildMasterKingBed(
  mats: PbrMaterialCatalog = getPbrMaterialCatalog()
): FurnitureFootprint {
  const group = new THREE.Group();
  group.name = 'MasterKingBed';
  const w = 2.0;
  const d = 2.15;

  // Dark timber bed frame base
  const baseGeo = new THREE.BoxGeometry(w, 0.28, d);
  const base = new THREE.Mesh(baseGeo, mats.doorTimber);
  base.position.set(0, 0.14, 0);
  base.castShadow = true;
  group.add(base);

  // High upholstered headboard with tufted seams
  const headGeo = new THREE.BoxGeometry(w + 0.1, 1.1, 0.12);
  const head = new THREE.Mesh(headGeo, mats.fabricTealAccent);
  head.position.set(0, 0.55, -d / 2 + 0.06);
  head.castShadow = true;
  group.add(head);

  // Soft linen mattress
  const mattGeo = new THREE.BoxGeometry(w - 0.06, 0.25, d - 0.1);
  const matt = new THREE.Mesh(mattGeo, mats.fabricLinen);
  matt.position.set(0, 0.28 + 0.125, 0.02);
  matt.castShadow = true;
  group.add(matt);

  // Folded duvet & pillows
  const duvetGeo = new THREE.BoxGeometry(w - 0.04, 0.08, d * 0.65);
  const duvet = new THREE.Mesh(duvetGeo, mats.fabricLinen);
  duvet.position.set(0, 0.44, 0.3);
  duvet.castShadow = true;
  group.add(duvet);

  // Teal runner at foot
  const runnerGeo = new THREE.BoxGeometry(w - 0.02, 0.02, 0.45);
  const runner = new THREE.Mesh(runnerGeo, mats.fabricTealAccent);
  runner.position.set(0, 0.485, 0.75);
  group.add(runner);

  // 4 Pillows (2 front, 2 back)
  for (const [px, pz] of [
    [-0.5, -0.65],
    [0.5, -0.65],
    [-0.5, -0.45],
    [0.5, -0.45],
  ]) {
    const pillowGeo = new THREE.BoxGeometry(0.65, 0.12, 0.38);
    const pillow = new THREE.Mesh(pillowGeo, mats.fabricLinen);
    pillow.position.set(px, 0.46, pz);
    pillow.rotation.x = -0.15;
    pillow.castShadow = true;
    group.add(pillow);
  }

  // Bedside Nightstands with glowing lamps
  for (const sx of [-w / 2 - 0.35, w / 2 + 0.35]) {
    const nsGeo = new THREE.BoxGeometry(0.48, 0.52, 0.42);
    const ns = new THREE.Mesh(nsGeo, mats.doorTimber);
    ns.position.set(sx, 0.26, -d / 2 + 0.25);
    ns.castShadow = true;
    group.add(ns);

    // Modern bedside table lamp with glowing shade
    const lampStem = new THREE.Mesh(
      new THREE.CylinderGeometry(0.015, 0.015, 0.35),
      mats.brushedBrass
    );
    lampStem.position.set(sx, 0.52 + 0.175, -d / 2 + 0.25);
    group.add(lampStem);

    const lampShade = new THREE.Mesh(
      new THREE.CylinderGeometry(0.12, 0.16, 0.2, 16),
      mats.spotlightGlow
    );
    lampShade.position.set(sx, 0.52 + 0.38, -d / 2 + 0.25);
    group.add(lampShade);
  }

  return { group, width: w + 1.2, depth: d };
}

/**
 * Builds L-shaped sectional sofa with coffee table, area rug & OLED TV media credenza
 */
export function buildLivingRoomSuite(
  mats: PbrMaterialCatalog = getPbrMaterialCatalog()
): FurnitureFootprint {
  const group = new THREE.Group();
  group.name = 'LivingRoomSuite';
  const totalW = 3.6;
  const totalD = 3.2;

  // 1. L-Shaped Sectional Sofa
  const sofaGroup = new THREE.Group();
  sofaGroup.name = 'LSofa';

  // Main 3-seat section (facing +Z)
  const mainSeatGeo = new THREE.BoxGeometry(2.4, 0.42, 0.95);
  const mainSeat = new THREE.Mesh(mainSeatGeo, mats.fabricLinen);
  mainSeat.position.set(0, 0.21, -0.6);
  mainSeat.castShadow = true;
  sofaGroup.add(mainSeat);

  // Main backrest
  const backGeo = new THREE.BoxGeometry(2.4, 0.46, 0.22);
  const back = new THREE.Mesh(backGeo, mats.fabricLinen);
  back.position.set(0, 0.58, -1.0);
  back.castShadow = true;
  sofaGroup.add(back);

  // Chaise section extending forward on the right (+X)
  const chaiseGeo = new THREE.BoxGeometry(0.95, 0.42, 1.4);
  const chaise = new THREE.Mesh(chaiseGeo, mats.fabricLinen);
  chaise.position.set(1.2 - 0.475, 0.21, 0.15);
  chaise.castShadow = true;
  sofaGroup.add(chaise);

  // Accent throw cushions
  for (const cx of [-0.7, 0.1, 0.6]) {
    const cushionGeo = new THREE.BoxGeometry(0.38, 0.38, 0.12);
    const cushion = new THREE.Mesh(cushionGeo, mats.fabricTealAccent);
    cushion.position.set(cx, 0.48, -0.85);
    cushion.rotation.z = 0.1;
    cushion.castShadow = true;
    sofaGroup.add(cushion);
  }

  group.add(sofaGroup);

  // 2. Large Designer Area Rug
  const rugGeo = new THREE.BoxGeometry(2.6, 0.015, 1.9);
  const rug = new THREE.Mesh(rugGeo, mats.fabricLinen);
  rug.position.set(0.1, 0.008, 0.15);
  rug.receiveShadow = true;
  group.add(rug);

  // 3. Polished Carrara Marble Coffee Table with Brass Base
  const tableGroup = new THREE.Group();
  tableGroup.position.set(0.1, 0, 0.15);

  const tableTopGeo = new THREE.BoxGeometry(1.1, 0.04, 0.65);
  const tableTop = new THREE.Mesh(tableTopGeo, mats.carraraMarble);
  tableTop.position.set(0, 0.4, 0);
  tableTop.castShadow = true;
  tableGroup.add(tableTop);

  // Brass legs
  for (const [lx, lz] of [
    [-0.45, -0.25],
    [0.45, -0.25],
    [-0.45, 0.25],
    [0.45, 0.25],
  ]) {
    const leg = new THREE.Mesh(
      new THREE.CylinderGeometry(0.018, 0.018, 0.38),
      mats.brushedBrass
    );
    leg.position.set(lx, 0.19, lz);
    leg.castShadow = true;
    tableGroup.add(leg);
  }
  group.add(tableGroup);

  // 4. Media Credenza Console & OLED TV (facing sofa)
  const tvGroup = new THREE.Group();
  tvGroup.position.set(0.1, 0, 1.45);

  const credGeo = new THREE.BoxGeometry(2.0, 0.45, 0.42);
  const cred = new THREE.Mesh(credGeo, mats.leatherDark);
  cred.position.set(0, 0.225, 0);
  cred.castShadow = true;
  tvGroup.add(cred);

  // Ultra-slim OLED TV Screen
  const tvScreen = new THREE.Mesh(
    new THREE.BoxGeometry(1.6, 0.9, 0.03),
    mats.leatherDark
  );
  tvScreen.position.set(0, 0.98, 0);
  tvScreen.castShadow = true;
  tvGroup.add(tvScreen);

  group.add(tvGroup);

  return { group, width: totalW, depth: totalD };
}

/**
 * Builds modern 6-seat dining table set with overhead pendant chandelier
 */
export function buildDiningSuite(
  mats: PbrMaterialCatalog = getPbrMaterialCatalog()
): FurnitureFootprint {
  const group = new THREE.Group();
  group.name = 'DiningSuite';
  const w = 1.9;
  const d = 1.0;
  const h = 0.76;

  // Solid wood dining tabletop with brass edge
  const topGeo = new THREE.BoxGeometry(w, 0.05, d);
  const top = new THREE.Mesh(topGeo, mats.doorTimber);
  top.position.set(0, h - 0.025, 0);
  top.castShadow = true;
  group.add(top);

  // 4 Legs
  for (const [lx, lz] of [
    [-w / 2 + 0.12, -d / 2 + 0.12],
    [w / 2 - 0.12, -d / 2 + 0.12],
    [-w / 2 + 0.12, d / 2 - 0.12],
    [w / 2 - 0.12, d / 2 - 0.12],
  ]) {
    const leg = new THREE.Mesh(
      new THREE.CylinderGeometry(0.03, 0.022, h - 0.05),
      mats.brushedBrass
    );
    leg.position.set(lx, (h - 0.05) / 2, lz);
    leg.castShadow = true;
    group.add(leg);
  }

  // 6 Upholstered Chairs (3 each side, pushed in)
  for (const cz of [-d / 2 - 0.22, d / 2 + 0.22]) {
    for (const cx of [-0.55, 0, 0.55]) {
      const chair = new THREE.Group();
      chair.position.set(cx, 0, cz);

      // Seat
      const seat = new THREE.Mesh(
        new THREE.BoxGeometry(0.44, 0.06, 0.44),
        mats.fabricLinen
      );
      seat.position.set(0, 0.45, 0);
      seat.castShadow = true;
      chair.add(seat);

      // Backrest
      const back = new THREE.Mesh(
        new THREE.BoxGeometry(0.42, 0.42, 0.04),
        mats.fabricTealAccent
      );
      back.position.set(0, 0.68, cz > 0 ? 0.2 : -0.2);
      back.castShadow = true;
      chair.add(back);

      group.add(chair);
    }
  }

  // Overhead Hanging Chandelier
  const chandelier = new THREE.Group();
  chandelier.position.set(0, 2.2, 0);

  const cord = new THREE.Mesh(
    new THREE.CylinderGeometry(0.008, 0.008, 0.65),
    mats.brushedBrass
  );
  cord.position.set(0, 0.325, 0);
  chandelier.add(cord);

  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(0.4, 0.02, 12, 32),
    mats.spotlightGlow
  );
  ring.rotation.x = Math.PI / 2;
  chandelier.add(ring);
  group.add(chandelier);

  return { group, width: w + 0.8, depth: d + 0.8 };
}

/**
 * Builds quartz kitchen run with waterfall island & modern bar stools
 */
export function buildKitchenSuite(
  length = 3.0,
  mats: PbrMaterialCatalog = getPbrMaterialCatalog()
): FurnitureFootprint {
  const group = new THREE.Group();
  group.name = 'KitchenSuite';

  // 1. Counter Run along wall
  const baseH = 0.85;
  const baseD = 0.65;

  const baseCab = new THREE.Mesh(
    new THREE.BoxGeometry(length, baseH, baseD),
    mats.leatherDark
  );
  baseCab.position.set(0, baseH / 2, 0);
  baseCab.castShadow = true;
  group.add(baseCab);

  // Polished quartz countertop
  const top = new THREE.Mesh(
    new THREE.BoxGeometry(length + 0.02, 0.05, baseD + 0.04),
    mats.carraraMarble
  );
  top.position.set(0, baseH + 0.025, 0);
  top.castShadow = true;
  group.add(top);

  // Induction cooktop (4 burner rings)
  const hob = new THREE.Mesh(
    new THREE.BoxGeometry(0.72, 0.015, 0.52),
    mats.doorBronzeFrame
  );
  hob.position.set(-length / 4, baseH + 0.055, 0);
  group.add(hob);

  // Undermount sink with gooseneck faucet
  const sink = new THREE.Mesh(
    new THREE.BoxGeometry(0.68, 0.02, 0.44),
    mats.doorBronzeFrame
  );
  sink.position.set(length / 4, baseH + 0.045, 0);
  group.add(sink);

  const faucet = new THREE.Mesh(
    new THREE.CylinderGeometry(0.015, 0.015, 0.32),
    mats.brushedBrass
  );
  faucet.position.set(length / 4, baseH + 0.2, -0.16);
  group.add(faucet);

  // 2. Breakfast Bar Island with 3 Bar Stools
  const islandW = 1.8;
  const islandD = 0.8;
  const islandH = 0.92;

  const islandGroup = new THREE.Group();
  islandGroup.position.set(0, 0, 1.4);

  // Waterfall marble top & side gables
  const islandTop = new THREE.Mesh(
    new THREE.BoxGeometry(islandW, 0.06, islandD),
    mats.carraraMarble
  );
  islandTop.position.set(0, islandH - 0.03, 0);
  islandTop.castShadow = true;
  islandGroup.add(islandTop);

  // Left gable
  const leftGable = new THREE.Mesh(
    new THREE.BoxGeometry(0.06, islandH - 0.06, islandD),
    mats.carraraMarble
  );
  leftGable.position.set(-islandW / 2 + 0.03, (islandH - 0.06) / 2, 0);
  islandGroup.add(leftGable);

  // Right gable
  const rightGable = new THREE.Mesh(
    new THREE.BoxGeometry(0.06, islandH - 0.06, islandD),
    mats.carraraMarble
  );
  rightGable.position.set(islandW / 2 - 0.03, (islandH - 0.06) / 2, 0);
  islandGroup.add(rightGable);

  // 3 Bar Stools
  for (const sx of [-0.5, 0, 0.5]) {
    const stool = new THREE.Group();
    stool.position.set(sx, 0, islandD / 2 + 0.22);

    const seat = new THREE.Mesh(
      new THREE.CylinderGeometry(0.18, 0.18, 0.05, 16),
      mats.leatherDark
    );
    seat.position.set(0, 0.65, 0);
    seat.castShadow = true;
    stool.add(seat);

    const leg = new THREE.Mesh(
      new THREE.CylinderGeometry(0.014, 0.014, 0.65),
      mats.brushedBrass
    );
    leg.position.set(0, 0.325, 0);
    stool.add(leg);

    islandGroup.add(stool);
  }

  group.add(islandGroup);

  return { group, width: length, depth: 2.2 };
}

/**
 * Builds luxury bathroom suite with floating vanity, LED backlit mirror & WC
 */
export function buildBathroomSuite(
  mats: PbrMaterialCatalog = getPbrMaterialCatalog()
): FurnitureFootprint {
  const group = new THREE.Group();
  group.name = 'BathroomSuite';

  // 1. Floating Vanity with Stone Top & Illuminated Mirror
  const vanityW = 0.85;
  const vanityD = 0.5;
  const vanityH = 0.55;

  const vanity = new THREE.Mesh(
    new THREE.BoxGeometry(vanityW, vanityH, vanityD),
    mats.doorTimber
  );
  vanity.position.set(-0.4, 0.55, 0);
  vanity.castShadow = true;
  group.add(vanity);

  const basin = new THREE.Mesh(
    new THREE.BoxGeometry(0.48, 0.12, 0.36),
    mats.carraraMarble
  );
  basin.position.set(-0.4, 0.88, 0);
  basin.castShadow = true;
  group.add(basin);

  // Backlit LED Mirror
  const mirror = new THREE.Mesh(
    new THREE.BoxGeometry(0.75, 0.9, 0.03),
    mats.spotlightGlow
  );
  mirror.position.set(-0.4, 1.6, -vanityD / 2);
  group.add(mirror);

  // 2. Wall-Hung Modern WC
  const wc = new THREE.Mesh(
    new THREE.BoxGeometry(0.38, 0.4, 0.58),
    mats.carraraMarble
  );
  wc.position.set(0.5, 0.3, 0);
  wc.castShadow = true;
  group.add(wc);

  return { group, width: 1.8, depth: 1.2 };
}

/**
 * Builds architectural indoor potted plant (Fiddle Leaf Fig / Monstera)
 */
export function buildArchitecturalPlant(
  mats: PbrMaterialCatalog = getPbrMaterialCatalog()
): THREE.Group {
  const group = new THREE.Group();
  group.name = 'ArchitecturalPlant';

  // Modern ceramic cylinder pot
  const pot = new THREE.Mesh(
    new THREE.CylinderGeometry(0.22, 0.18, 0.45, 16),
    mats.carraraMarble
  );
  pot.position.set(0, 0.225, 0);
  pot.castShadow = true;
  group.add(pot);

  // Cluster of lush organic foliage blobs
  const leavesMat = new THREE.MeshStandardMaterial({
    color: 0x3d7036,
    roughness: 0.65,
    metalness: 0.0,
  });

  for (let i = 0; i < 5; i++) {
    const angle = (i / 5) * Math.PI * 2;
    const leaf = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.18 + (i % 2) * 0.05, 2),
      leavesMat
    );
    leaf.position.set(
      Math.cos(angle) * 0.12,
      0.55 + i * 0.12,
      Math.sin(angle) * 0.12
    );
    leaf.scale.set(1.1, 1.3, 1.0);
    leaf.castShadow = true;
    group.add(leaf);
  }

  return group;
}

/**
 * Builds expansive luxury outdoor patio / deck lounge suite (as in reference image 1000204412.jpg)
 * Includes teak wood frame daybed / sofa, off-white linen cushions, low slatted coffee table & patio planter
 */
export function buildOutdoorDeckSuite(
  mats: PbrMaterialCatalog = getPbrMaterialCatalog()
): FurnitureFootprint {
  const group = new THREE.Group();
  group.name = 'OutdoorDeckSuite';

  // 1. Teak slatted outdoor lounge sofa
  const sofaW = 2.4;
  const sofaD = 0.95;
  const sofaBase = new THREE.Mesh(
    new THREE.BoxGeometry(sofaW, 0.18, sofaD),
    mats.doorTimber
  );
  sofaBase.position.set(0, 0.09, 0);
  sofaBase.castShadow = true;
  group.add(sofaBase);

  // Soft cream weather-resistant seat cushions
  const cushionW = (sofaW - 0.1) / 3;
  for (let i = 0; i < 3; i++) {
    const seat = new THREE.Mesh(
      new THREE.BoxGeometry(cushionW - 0.03, 0.14, sofaD - 0.15),
      mats.fabricLinen
    );
    seat.position.set(-sofaW / 2 + 0.05 + cushionW * i + cushionW / 2, 0.25, 0.05);
    seat.castShadow = true;
    group.add(seat);

    // Backrest cushion
    const back = new THREE.Mesh(
      new THREE.BoxGeometry(cushionW - 0.03, 0.32, 0.14),
      mats.fabricLinen
    );
    back.position.set(-sofaW / 2 + 0.05 + cushionW * i + cushionW / 2, 0.44, -sofaD / 2 + 0.12);
    back.castShadow = true;
    group.add(back);
  }

  // 2. Low Teak Patio Coffee Table
  const tableW = 1.2;
  const tableD = 0.65;
  const table = new THREE.Mesh(
    new THREE.BoxGeometry(tableW, 0.28, tableD),
    mats.doorTimber
  );
  table.position.set(0, 0.14, sofaD / 2 + tableD / 2 + 0.4);
  table.castShadow = true;
  group.add(table);

  // Marble serving tray on table
  const tray = new THREE.Mesh(
    new THREE.BoxGeometry(0.42, 0.02, 0.3),
    mats.carraraMarble
  );
  tray.position.set(0, 0.29, sofaD / 2 + tableD / 2 + 0.4);
  group.add(tray);

  // 3. Potted Patio Palm
  const palm = buildArchitecturalPlant(mats);
  palm.position.set(sofaW / 2 + 0.55, 0, -sofaD / 2);
  group.add(palm);

  return { group, width: sofaW + 1.2, depth: sofaD + 1.4 };
}

