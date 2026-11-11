// frontend/src/features/plan-viewer/builders/buildRailings.tsx
import * as THREE from 'three';
import {
  getPbrMaterialCatalog,
  type PbrMaterialCatalog,
} from '../materials/materials';

export interface StaircaseConfig {
  center: { x: number; y: number };
  width: number;
  depth: number;
  totalHeight?: number;
  angle?: number;
}

/**
 * Builds stepped U-turn staircase with polished wood treads, white risers, landing & glass balustrade
 */
export function buildStaircaseMesh(
  config: StaircaseConfig,
  mats: PbrMaterialCatalog = getPbrMaterialCatalog()
): THREE.Group {
  const group = new THREE.Group();
  group.name = 'UturnStaircase';
  const totalH = config.totalHeight || 2.9;
  const numStepsPerFlight = 8;
  const riserH = totalH / (numStepsPerFlight * 2);
  const flightW = (config.width - 0.2) / 2;
  const treadD = (config.depth - 1.0) / numStepsPerFlight;

  // 1. Lower Flight (First half)
  for (let i = 0; i < numStepsPerFlight; i++) {
    const stepGroup = new THREE.Group();

    // White riser
    const riserGeo = new THREE.BoxGeometry(flightW, riserH, 0.04);
    const riserMesh = new THREE.Mesh(riserGeo, mats.interiorPlaster);
    riserMesh.position.set(0, riserH / 2, 0);
    riserMesh.castShadow = true;
    stepGroup.add(riserMesh);

    // Polished wood tread
    const treadGeo = new THREE.BoxGeometry(flightW + 0.04, 0.035, treadD + 0.04);
    const treadMesh = new THREE.Mesh(treadGeo, mats.herringboneOak);
    treadMesh.position.set(0, riserH, treadD / 2);
    treadMesh.castShadow = true;
    stepGroup.add(treadMesh);

    stepGroup.position.set(-flightW / 2 - 0.05, i * riserH, i * treadD);
    group.add(stepGroup);
  }

  // 2. Intermediate Landing Slab
  const landingH = totalH / 2;
  const landingGeo = new THREE.BoxGeometry(config.width, 0.12, 1.0);
  const landingMesh = new THREE.Mesh(landingGeo, mats.herringboneOak);
  landingMesh.position.set(0, landingH, numStepsPerFlight * treadD + 0.5);
  landingMesh.castShadow = true;
  group.add(landingMesh);

  // 3. Upper Flight (Second half returning)
  for (let i = 0; i < numStepsPerFlight; i++) {
    const stepGroup = new THREE.Group();

    const riserGeo = new THREE.BoxGeometry(flightW, riserH, 0.04);
    const riserMesh = new THREE.Mesh(riserGeo, mats.interiorPlaster);
    riserMesh.position.set(0, riserH / 2, 0);
    riserMesh.castShadow = true;
    stepGroup.add(riserMesh);

    const treadGeo = new THREE.BoxGeometry(flightW + 0.04, 0.035, treadD + 0.04);
    const treadMesh = new THREE.Mesh(treadGeo, mats.herringboneOak);
    treadMesh.position.set(0, riserH, -treadD / 2);
    treadMesh.castShadow = true;
    stepGroup.add(treadMesh);

    stepGroup.position.set(flightW / 2 + 0.05, landingH + i * riserH, numStepsPerFlight * treadD - i * treadD);
    group.add(stepGroup);
  }

  // 4. Glass Balustrade & Stainless Steel Handrail along the flight center
  const balustradeGeo = new THREE.BoxGeometry(0.015, 0.95, config.depth * 0.9);
  const balustrade = new THREE.Mesh(balustradeGeo, mats.balconyGlass);
  balustrade.position.set(0, totalH * 0.5, config.depth * 0.45);
  group.add(balustrade);

  const handrailGeo = new THREE.CylinderGeometry(0.02, 0.02, config.depth * 0.9, 12);
  handrailGeo.rotateX(Math.PI / 2);
  const handrail = new THREE.Mesh(handrailGeo, mats.doorBronzeFrame);
  handrail.position.set(0, totalH * 0.5 + 0.48, config.depth * 0.45);
  group.add(handrail);

  group.position.set(config.center.x, 0, config.center.y);
  group.rotation.y = config.angle || 0;
  return group;
}

/**
 * Builds contemporary architectural glass balcony railing
 */
export function buildBalconyRailing(
  length: number,
  mats: PbrMaterialCatalog = getPbrMaterialCatalog()
): THREE.Group {
  const group = new THREE.Group();
  group.name = 'BalconyGlassRailing';

  const railH = 1.05;

  // Tempered safety glass panel
  const glassGeo = new THREE.BoxGeometry(length, railH, 0.016);
  const glass = new THREE.Mesh(glassGeo, mats.balconyGlass);
  glass.position.set(length / 2, railH / 2, 0);
  glass.castShadow = false;
  group.add(glass);

  // Top capping handrail
  const topRailGeo = new THREE.BoxGeometry(length, 0.04, 0.05);
  const topRail = new THREE.Mesh(topRailGeo, mats.doorBronzeFrame);
  topRail.position.set(length / 2, railH - 0.02, 0);
  topRail.castShadow = true;
  group.add(topRail);

  // Bottom clamping spigots
  const numSpigots = Math.max(2, Math.round(length / 0.8));
  const spigotGeo = new THREE.BoxGeometry(0.05, 0.12, 0.06);
  for (let i = 0; i <= numSpigots; i++) {
    const sx = (length / numSpigots) * i;
    const spigot = new THREE.Mesh(spigotGeo, mats.doorBronzeFrame);
    spigot.position.set(sx, 0.06, 0);
    spigot.castShadow = true;
    group.add(spigot);
  }

  return group;
}

