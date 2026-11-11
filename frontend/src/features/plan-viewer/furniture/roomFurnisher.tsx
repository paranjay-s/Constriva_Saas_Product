// frontend/src/features/plan-viewer/furniture/roomFurnisher.tsx
import * as THREE from 'three';
import {
  getPbrMaterialCatalog,
  type PbrMaterialCatalog,
} from '../materials/materials';
import {
  buildMasterKingBed,
  buildLivingRoomSuite,
  buildDiningSuite,
  buildKitchenSuite,
  buildBathroomSuite,
  buildArchitecturalPlant,
  buildOutdoorDeckSuite,
} from './furnitureLibrary';

export interface FurnisherRoom {
  id: string;
  name?: string;
  type?: string;
  kind?: string;
  polygon: { x: number; y: number }[];
}

export interface FurnishingResult {
  group: THREE.Group;
  setConstructionPhase: (phase: number) => void;
}

/**
 * Intelligent auto-staging solver: reads room geometry, finds solid anchor walls & places high-detail PBR suites
 */
export function furnishRoomsWithPbr(
  rooms: FurnisherRoom[],
  mats: PbrMaterialCatalog = getPbrMaterialCatalog()
): FurnishingResult {
  const group = new THREE.Group();
  group.name = 'AutoStagedFurniture';

  for (const r of rooms) {
    if (r.polygon.length < 3) continue;

    const kind = (r.kind || '').toLowerCase();
    const type = (r.type || '').toLowerCase();
    const name = (r.name || r.id).toLowerCase();

    // Skip open shafts and voids
    if (kind === 'void' || name.includes('shaft') || name.includes('void')) {
      continue;
    }

    // Compute room centroid & bounding box
    let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
    let sumX = 0, sumZ = 0;
    for (const p of r.polygon) {
      if (p.x < minX) minX = p.x;
      if (p.x > maxX) maxX = p.x;
      if (p.y < minZ) minZ = p.y;
      if (p.y > maxZ) maxZ = p.y;
      sumX += p.x;
      sumZ += p.y;
    }

    const n = r.polygon.length;
    const cx = sumX / n;
    const cz = sumZ / n;
    const rw = maxX - minX;
    const rd = maxZ - minZ;
    const area = rw * rd;

    // 1. Bedroom Staging
    if (type.includes('bed') || name.includes('bed')) {
      if (rw >= 2.6 && rd >= 2.6) {
        const bed = buildMasterKingBed(mats);
        // Place bed head against North wall (-Z in Three.js)
        bed.group.position.set(cx, 0, minZ + 1.25);
        group.add(bed.group);

        // Corner potted plant
        if (rw >= 3.2) {
          const plant = buildArchitecturalPlant(mats);
          plant.position.set(maxX - 0.45, 0, maxZ - 0.45);
          group.add(plant);
        }
      }
    }
    // 2. Living / Drawing Room Staging
    else if (
      type.includes('living') ||
      type.includes('drg') ||
      type.includes('drawing') ||
      name.includes('living') ||
      name.includes('hall') ||
      name.includes('lounge')
    ) {
      if (area >= 12.0) {
        const livingSuite = buildLivingRoomSuite(mats);
        livingSuite.group.position.set(cx, 0, cz);
        group.add(livingSuite.group);

        // Corner plant
        const plant = buildArchitecturalPlant(mats);
        plant.position.set(minX + 0.5, 0, minZ + 0.5);
        group.add(plant);
      }
    }
    // 3. Dining Area Staging
    else if (type.includes('dining') || name.includes('dining')) {
      if (rw >= 2.2 && rd >= 2.2) {
        const dining = buildDiningSuite(mats);
        dining.group.position.set(cx, 0, cz);
        group.add(dining.group);
      }
    }
    // 4. Kitchen Staging
    else if (type.includes('kitchen') || name.includes('kitchen')) {
      if (rw >= 2.2) {
        const runLen = Math.max(2.2, Math.min(rw - 0.5, 3.6));
        const kitchen = buildKitchenSuite(runLen, mats);
        kitchen.group.position.set(cx, 0, minZ + 0.4);
        group.add(kitchen.group);
      }
    }
    // 5. Bathroom / Toilet Staging
    else if (
      type.includes('bath') ||
      type.includes('toilet') ||
      type.includes('wc') ||
      name.includes('bath') ||
      name.includes('toilet')
    ) {
      if (rw >= 1.4 && rd >= 1.4) {
        const bath = buildBathroomSuite(mats);
        bath.group.position.set(cx, 0, minZ + 0.4);
        group.add(bath.group);
      }
    }
    // 6. Balcony / Sun Terrace / Deck / Patio (Reference 1000204412.jpg)
    else if (
      type.includes('balcony') ||
      type.includes('terrace') ||
      type.includes('deck') ||
      type.includes('patio') ||
      type.includes('sitout') ||
      name.includes('balcony') ||
      name.includes('terrace') ||
      name.includes('deck') ||
      name.includes('patio') ||
      name.includes('sitout')
    ) {
      if (rw >= 2.0 && rd >= 1.6) {
        const deckSuite = buildOutdoorDeckSuite(mats);
        deckSuite.group.position.set(cx, 0, cz);
        group.add(deckSuite.group);
      } else {
        const plant = buildArchitecturalPlant(mats);
        plant.position.set(cx, 0, cz);
        group.add(plant);
      }
    }
  }

  // 4D timeline animation support (furniture appears in Phase 4: >= 0.8)
  const setConstructionPhase = (phase: number) => {
    const clamped = Math.max(0, Math.min(1, phase));
    group.visible = clamped >= 0.8;
  };

  return { group, setConstructionPhase };
}

