// furniture/builders/puja.ts
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import type { MaterialLibrary } from '../../materials/materials';
import { createContactBlob } from '../../build/ao';
import type { FurnitureMeshResult } from './bed';

/**
 * Builds traditional wooden Mandir / Puja shrine unit with warm gold accent
 * Dimensions: 0.9m w x 0.45m d x 1.6m h
 */
export function buildPujaUnit(mats: MaterialLibrary): FurnitureMeshResult {
  const group = new THREE.Group();
  group.name = 'PujaUnit';
  const w = 0.9;
  const d = 0.45;
  const h = 1.6;

  group.add(createContactBlob(w, d, mats));

  // Lower storage plinth / cabinet
  const baseH = 0.48;
  const baseGeo = new RoundedBoxGeometry(w, baseH, d, 3, 0.02);
  const base = new THREE.Mesh(baseGeo, mats.woodFurniture);
  base.position.set(0, baseH / 2, 0);
  base.castShadow = true;
  base.receiveShadow = true;
  group.add(base);

  // Shrine canopy back panel
  const backGeo = new THREE.BoxGeometry(w, h - baseH, 0.05);
  const back = new THREE.Mesh(backGeo, mats.woodFurniture);
  back.position.set(0, baseH + (h - baseH) / 2, -d / 2 + 0.025);
  back.castShadow = true;
  group.add(back);

  // Top canopy roof
  const roofGeo = new RoundedBoxGeometry(w + 0.06, 0.08, d + 0.04, 2, 0.02);
  const roof = new THREE.Mesh(roofGeo, mats.woodFurniture);
  roof.position.set(0, h - 0.04, 0);
  roof.castShadow = true;
  group.add(roof);

  // Warm gold accent bell / dome pinnacle (#C9A24B)
  const domeMat = new THREE.MeshStandardMaterial({
    color: 0xc9a24b,
    metalness: 0.5,
    roughness: 0.3,
  });
  const domeGeo = new THREE.ConeGeometry(0.08, 0.18, 16);
  const dome = new THREE.Mesh(domeGeo, domeMat);
  dome.position.set(0, h + 0.09, 0);
  dome.castShadow = true;
  group.add(dome);

  // Diya oil lamp shelf in center
  const shelfGeo = new THREE.BoxGeometry(w - 0.1, 0.03, d - 0.1);
  const shelf = new THREE.Mesh(shelfGeo, mats.stone);
  shelf.position.set(0, baseH + 0.015, 0);
  group.add(shelf);

  return { group, footprint: { w, d } };
}

