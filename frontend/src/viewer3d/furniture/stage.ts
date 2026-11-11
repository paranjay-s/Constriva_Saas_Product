// furniture/stage.ts
import * as THREE from 'three';
import type { MaterialLibrary } from '../materials/materials';
import type { FurnitureItem, Plan, Room, Vec2 } from '../types';
import {
  minimumAreaOBB,
  polygonArea,
  type OBB,
} from '../utils/geometry';
import {
  canPlaceBox,
  computeRoomKeepOuts,
  type PlacedBox,
} from './layout';
import {
  buildDoubleBed,
  buildNightstand,
  buildWardrobe,
  buildSofa3,
  buildSofaL,
  buildCoffeeTable,
  buildTvUnit,
  buildLivingRug,
  buildArmchair,
  buildDiningTable,
  buildKitchenRun,
  buildKitchenIsland,
  buildWc,
  buildVanity,
  buildShower,
  buildPujaUnit,
  buildCar,
} from './builders';
import { buildPottedPlant, buildTerraceShrub } from './plants';

export function stagePlan(plan: Plan, mats: MaterialLibrary): THREE.Group {
  const rootGroup = new THREE.Group();
  rootGroup.name = 'StagedFurniture';

  // If explicit furniture items are provided in the plan JSON, build those
  if (plan.furniture && plan.furniture.length > 0) {
    for (const item of plan.furniture) {
      const mesh = buildExplicitItem(item, mats);
      if (mesh) {
        mesh.position.set(item.position.x, 0, item.position.y);
        mesh.rotation.y = item.rotation || 0;
        rootGroup.add(mesh);
      }
    }
    return rootGroup;
  }

  // Otherwise, run deterministic auto-staging per room
  for (const room of plan.rooms) {
    const area = polygonArea(room.polygon);
    if (area < 1.0) continue; // Skip tiny utility shafts

    const obb = minimumAreaOBB(room.polygon);
    const keepOuts = computeRoomKeepOuts(room, plan.walls, plan.openings);
    const placedBoxes: PlacedBox[] = [];

    const place = (
      mesh: THREE.Group,
      w: number,
      d: number,
      x: number,
      z: number,
      angle: number
    ): boolean => {
      const box: PlacedBox = {
        center: { x, y: z },
        width: w,
        depth: d,
        angle,
      };

      if (!canPlaceBox(box, room.polygon, placedBoxes, keepOuts)) {
        return false;
      }

      mesh.position.set(x, 0, z);
      mesh.rotation.y = angle;
      rootGroup.add(mesh);
      placedBoxes.push(box);
      return true;
    };

    stageRoom(room, obb, area, mats, place);
  }

  return rootGroup;
}

function stageRoom(
  room: Room,
  obb: OBB,
  area: number,
  mats: MaterialLibrary,
  place: (mesh: THREE.Group, w: number, d: number, x: number, z: number, angle: number) => boolean
) {
  const { center, width, depth, angle } = obb;
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);

  // Local to world coordinate transformer
  const toWorld = (lu: number, lv: number): Vec2 => {
    return {
      x: center.x + (lu * cos - lv * sin),
      y: center.y + (lu * sin + lv * cos),
    };
  };

  switch (room.type) {
    case 'bedroom': {
      // Double bed headboard placed against South side of OBB, facing +V (inward)
      const bed = buildDoubleBed(mats);
      const bedCenter = toWorld(0, -depth / 2 + 1.1);
      const bedPlaced = place(bed.group, 1.6, 2.05, bedCenter.x, bedCenter.y, angle);

      if (bedPlaced) {
        // Nightstands on both sides of bed
        if (width >= 2.8) {
          const leftNs = buildNightstand(mats);
          const leftPos = toWorld(-1.05, -depth / 2 + 0.3);
          place(leftNs.group, 0.45, 0.4, leftPos.x, leftPos.y, angle);

          const rightNs = buildNightstand(mats);
          const rightPos = toWorld(1.05, -depth / 2 + 0.3);
          place(rightNs.group, 0.45, 0.4, rightPos.x, rightPos.y, angle);
        }

        // Wardrobe against North wall if room is >= 9 m²
        if (area >= 9.0 && depth >= 3.2) {
          const wardrobe = buildWardrobe(mats, Math.min(width * 0.6, 1.8));
          const wPos = toWorld(0, depth / 2 - 0.35);
          place(wardrobe.group, 1.8, 0.6, wPos.x, wPos.y, angle + Math.PI);
        }
      }
      break;
    }

    case 'living':
    case 'drawing': {
      // Sectional L-Sofa or 3-Seater Sofa against wall
      const useLSofa = area >= 16.0 && width >= 3.6 && depth >= 3.2;
      const sofa = useLSofa ? buildSofaL(mats) : buildSofa3(mats);
      const sofaOffsetV = -depth / 2 + (useLSofa ? 0.95 : 0.6);
      const sofaPos = toWorld(0, sofaOffsetV);
      const sofaPlaced = place(
        sofa.group,
        sofa.footprint.w,
        sofa.footprint.d,
        sofaPos.x,
        sofaPos.y,
        angle
      );

      if (sofaPlaced) {
        // Media TV Console opposite the sofa
        const tv = buildTvUnit(mats);
        const tvPos = toWorld(0, depth / 2 - 0.3);
        place(tv.group, 1.6, 0.4, tvPos.x, tvPos.y, angle + Math.PI);

        // Living room rug centered between sofa and TV
        const rug = buildLivingRug(mats, Math.min(width * 0.7, 2.4), 1.6);
        const rugPos = toWorld(0, 0.1);
        place(rug.group, 2.4, 1.6, rugPos.x, rugPos.y, angle);

        // Coffee table on top of rug
        const table = buildCoffeeTable(mats);
        place(table.group, 1.0, 0.6, rugPos.x, rugPos.y, angle);

        // Potted plant in corner
        const plant = buildPottedPlant(mats);
        const plantPos = toWorld(width / 2 - 0.45, -depth / 2 + 0.45);
        place(plant.group, 0.5, 0.5, plantPos.x, plantPos.y, 0);

        // Armchair if living room is generous
        if (area >= 20.0 && width >= 4.2) {
          const chair = buildArmchair(mats);
          const chairPos = toWorld(-width / 2 + 0.7, 0.2);
          place(chair.group, 0.85, 0.85, chairPos.x, chairPos.y, angle + 0.6);
        }
      }
      break;
    }

    case 'dining': {
      // Dining table set centered in room OBB
      const dining = buildDiningTable(mats);
      const diningPlaced = place(
        dining.group,
        dining.footprint.w,
        dining.footprint.d,
        center.x,
        center.y,
        angle
      );

      if (diningPlaced) {
        // Corner decorative plant
        const plant = buildPottedPlant(mats);
        const plantPos = toWorld(width / 2 - 0.4, depth / 2 - 0.4);
        place(plant.group, 0.5, 0.5, plantPos.x, plantPos.y, 0);
      }
      break;
    }

    case 'kitchen': {
      // Kitchen counter run along the longest wall
      const runLen = Math.max(1.8, Math.min(width - 0.6, 3.2));
      const kitchenRun = buildKitchenRun(mats, runLen);
      const runPos = toWorld(0, -depth / 2 + 0.35);
      const runPlaced = place(
        kitchenRun.group,
        runLen,
        0.6,
        runPos.x,
        runPos.y,
        angle
      );

      // Breakfast island if kitchen is spacious
      if (runPlaced && area >= 10.0 && depth >= 2.8) {
        const island = buildKitchenIsland(mats, 1.6, 0.75);
        const islandPos = toWorld(0, 0.4);
        place(island.group, 1.6, 0.75, islandPos.x, islandPos.y, angle);
      }
      break;
    }

    case 'toilet':
    case 'wash': {
      // Toilet WC against wall
      const wc = buildWc(mats);
      const wcPos = toWorld(-width / 2 + 0.4, -depth / 2 + 0.4);
      place(wc.group, 0.4, 0.65, wcPos.x, wcPos.y, angle);

      // Vanity on adjacent or opposite wall
      const vanity = buildVanity(mats, 0.7);
      const vanityPos = toWorld(width / 2 - 0.45, -depth / 2 + 0.35);
      place(vanity.group, 0.7, 0.45, vanityPos.x, vanityPos.y, angle);

      // Shower in far corner if space permits
      if (area >= 3.2 && depth >= 1.8) {
        const shower = buildShower(mats, 0.9);
        const showerPos = toWorld(width / 2 - 0.5, depth / 2 - 0.5);
        place(shower.group, 0.9, 0.9, showerPos.x, showerPos.y, angle);
      }
      break;
    }

    case 'puja': {
      const puja = buildPujaUnit(mats);
      const pujaPos = toWorld(0, -depth / 2 + 0.28);
      place(puja.group, 0.9, 0.45, pujaPos.x, pujaPos.y, angle);
      break;
    }

    case 'parking': {
      if (
        (width >= 2.4 && depth >= 4.2) ||
        (width >= 4.2 && depth >= 2.4)
      ) {
        const carAngle = width >= depth ? angle + Math.PI / 2 : angle;
        const car = buildCar(mats);
        place(car.group, 1.8, 4.2, center.x, center.y, carAngle);
      }
      break;
    }

    case 'balcony':
    case 'terrace': {
      // Lush green shrubs on outdoor balconies
      const shrub1 = buildTerraceShrub(mats, 101);
      const pos1 = toWorld(-width / 2 + 0.4, -depth / 2 + 0.4);
      place(shrub1.group, 0.65, 0.65, pos1.x, pos1.y, 0);

      if (width >= 2.5) {
        const shrub2 = buildTerraceShrub(mats, 202);
        const pos2 = toWorld(width / 2 - 0.4, depth / 2 - 0.4);
        place(shrub2.group, 0.65, 0.65, pos2.x, pos2.y, 0);
      }
      break;
    }

    default:
      break;
  }
}

function buildExplicitItem(
  item: FurnitureItem,
  mats: MaterialLibrary
): THREE.Group | null {
  const t = item.type.toLowerCase();
  if (t.includes('bed')) return buildDoubleBed(mats).group;
  if (t.includes('sofa')) return buildSofa3(mats).group;
  if (t.includes('table') || t.includes('dining')) return buildDiningTable(mats).group;
  if (t.includes('tv')) return buildTvUnit(mats).group;
  if (t.includes('wc') || t.includes('toilet')) return buildWc(mats).group;
  if (t.includes('vanity')) return buildVanity(mats).group;
  if (t.includes('shower')) return buildShower(mats).group;
  if (t.includes('puja')) return buildPujaUnit(mats).group;
  if (t.includes('plant')) return buildPottedPlant(mats).group;
  if (t.includes('car')) return buildCar(mats).group;
  return null;
}
