// furniture/plants.ts
import * as THREE from 'three';
import type { MaterialLibrary } from '../materials/materials';
import { createContactBlob } from '../build/ao';
import { mulberry32 } from '../utils/rng';
import type { FurnitureMeshResult } from './builders/bed';

/**
 * Builds stylish architectural indoor potted plant
 * Pot cylinder + 3-5 organic foliage leaf cluster blobs in foliageA/B/C
 * Dimensions: ~0.5m diameter x 0.95m height
 */
export function buildPottedPlant(
  mats: MaterialLibrary,
  seed = 42
): FurnitureMeshResult {
  const group = new THREE.Group();
  group.name = 'PottedPlant';
  const rng = mulberry32(seed);

  // Soft contact blob under pot
  group.add(createContactBlob(0.55, 0.55, mats));

  // Modern tapered ceramic planter pot
  const potGeo = new THREE.CylinderGeometry(0.22, 0.16, 0.42, 16);
  const pot = new THREE.Mesh(potGeo, mats.pot);
  pot.position.set(0, 0.21, 0);
  pot.castShadow = true;
  pot.receiveShadow = true;
  group.add(pot);

  // Dark soil surface
  const soilGeo = new THREE.CircleGeometry(0.21, 16);
  soilGeo.rotateX(-Math.PI / 2);
  const soil = new THREE.Mesh(soilGeo, mats.stoolDark);
  soil.position.set(0, 0.415, 0);
  group.add(soil);

  // 3-5 Organic foliage blobs
  const foliageMats = [mats.foliageA, mats.foliageB, mats.foliageC];
  const numBlobs = 4;
  const offsets = [
    { x: 0, y: 0.65, z: 0, r: 0.24 },
    { x: 0.12, y: 0.76, z: 0.08, r: 0.21 },
    { x: -0.11, y: 0.72, z: -0.06, r: 0.19 },
    { x: 0.04, y: 0.86, z: -0.07, r: 0.18 },
  ];

  for (let i = 0; i < numBlobs; i++) {
    const off = offsets[i];
    const leafGeo = new THREE.IcosahedronGeometry(off.r, 2);
    const leafMat = foliageMats[i % foliageMats.length];
    const leafMesh = new THREE.Mesh(leafGeo, leafMat);
    leafMesh.position.set(
      off.x + (rng() - 0.5) * 0.04,
      off.y + (rng() - 0.5) * 0.04,
      off.z + (rng() - 0.5) * 0.04
    );
    leafMesh.scale.set(1 + rng() * 0.1, 1 + rng() * 0.15, 1 + rng() * 0.1);
    leafMesh.castShadow = true;
    leafMesh.receiveShadow = true;
    group.add(leafMesh);
  }

  return { group, footprint: { w: 0.5, d: 0.5 } };
}

/**
 * Builds decorative lush outdoor planter for balcony / terrace
 */
export function buildTerraceShrub(
  mats: MaterialLibrary,
  seed = 101
): FurnitureMeshResult {
  const group = new THREE.Group();
  group.name = 'TerraceShrub';
  const rng = mulberry32(seed);

  group.add(createContactBlob(0.65, 0.65, mats));

  // Low wide bowl planter
  const bowlGeo = new THREE.CylinderGeometry(0.28, 0.18, 0.32, 16);
  const bowl = new THREE.Mesh(bowlGeo, mats.pot);
  bowl.position.set(0, 0.16, 0);
  bowl.castShadow = true;
  group.add(bowl);

  // Cluster of lush greenery
  const foliageMats = [mats.foliageB, mats.foliageA, mats.foliageC];
  for (let i = 0; i < 5; i++) {
    const angle = (i / 5) * Math.PI * 2;
    const r = 0.14 + rng() * 0.06;
    const bx = Math.cos(angle) * r;
    const bz = Math.sin(angle) * r;
    const by = 0.42 + rng() * 0.18;

    const leafGeo = new THREE.IcosahedronGeometry(0.18 + rng() * 0.05, 2);
    const leaf = new THREE.Mesh(leafGeo, foliageMats[i % foliageMats.length]);
    leaf.position.set(bx, by, bz);
    leaf.castShadow = true;
    group.add(leaf);
  }

  return { group, footprint: { w: 0.65, d: 0.65 } };
}

