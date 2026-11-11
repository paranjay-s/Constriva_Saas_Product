import { useMemo } from 'react';
import type { Room } from '../../../types';
import type { MaterialTheme } from '../materials/materials';
import { categorizeRoom } from '../materials/materials';
import {
  BedDouble,
  Wardrobe,
  LivingSet,
  DiningSet,
  KitchenSet,
  BathroomSuite,
  BalconySet,
  LawnGardenSet,
  StaircaseSet,
  UtilitySet,
} from './furnitureLibrary';

interface RoomFurnisherProps {
  room: Room;
  theme: MaterialTheme;
}

export function RoomFurnisher({ room, theme }: RoomFurnisherProps) {
  const polygon = room.polygon || [];
  if (polygon.length === 0) return null;

  // Compute 2D bounding box
  const { minX, maxX, minZ, cx, cz, width, depth } = useMemo(() => {
    let x0 = Infinity;
    let x1 = -Infinity;
    let z0 = Infinity;
    let z1 = -Infinity;

    for (const [x, z] of polygon) {
      if (x < x0) x0 = x;
      if (x > x1) x1 = x;
      if (z < z0) z0 = z;
      if (z > z1) z1 = z;
    }

    const w = x1 - x0;
    const d = z1 - z0;
    return {
      minX: x0,
      maxX: x1,
      minZ: z0,
      maxZ: z1,
      cx: x0 + w / 2,
      cz: z0 + d / 2,
      width: w,
      depth: d,
    };
  }, [polygon]);

  const category = useMemo(() => categorizeRoom(room.name, room.id), [room.name, room.id]);
  const isCombinedLivingDining = useMemo(() => {
    const n = (room.name || '').toLowerCase();
    return (n.includes('living') && n.includes('dining')) || width >= 5.5;
  }, [room.name, width]);

  // If room is too small, don't overcrowd
  if (width < 1.6 || depth < 1.6) return null;

  // Dedicated Staircase room rendering
  const isStaircase = (room.name || '').toLowerCase().includes('stair') || (room.id || '').toLowerCase().includes('stair');
  if (isStaircase) {
    const steps = Math.max(7, Math.min(12, Math.floor(depth / 0.28)));
    const stairW = Math.max(1.1, Math.min(1.5, width * 0.45));
    return (
      <group position={[cx, 0, cz]}>
        <StaircaseSet theme={theme} stepsCount={steps} width={stairW} />
      </group>
    );
  }

  switch (category) {
    case 'bedroom': {
      // Place bed along one wall facing into room, wardrobe against side
      const bedX = cx;
      const bedZ = minZ + 1.35;
      const wardrobeX = maxX - 0.45;
      const wardrobeZ = cz;
      const wardrobeW = Math.min(1.8, depth * 0.55);

      return (
        <group>
          {/* Bed */}
          <group position={[bedX, 0, bedZ]}>
            <BedDouble theme={theme} />
          </group>

          {/* Wardrobe along side wall */}
          {width >= 3.6 && (
            <group position={[wardrobeX, 0, wardrobeZ]} rotation={[0, -Math.PI / 2, 0]}>
              <Wardrobe width={wardrobeW} theme={theme} />
            </group>
          )}
        </group>
      );
    }

    case 'living': {
      if (isCombinedLivingDining) {
        // Split room: Living on left, Dining on right
        const livingCx = minX + width * 0.35;
        const diningCx = minX + width * 0.75;

        return (
          <group>
            {/* Living Zone */}
            <group position={[livingCx, 0, cz]}>
              <LivingSet theme={theme} />
            </group>

            {/* Dining Zone */}
            <group position={[diningCx, 0, cz]}>
              <DiningSet theme={theme} />
            </group>
          </group>
        );
      }

      return (
        <group position={[cx, 0, cz]}>
          <LivingSet theme={theme} />
        </group>
      );
    }

    case 'dining': {
      return (
        <group position={[cx, 0, cz]}>
          <DiningSet theme={theme} />
        </group>
      );
    }

    case 'kitchen': {
      // Align counter along north wall of kitchen
      const counterLen = Math.max(2.0, Math.min(3.6, width * 0.85));
      const counterZ = minZ + 0.45;

      return (
        <group position={[minX + counterLen / 2 + 0.2, 0, counterZ]}>
          <KitchenSet length={counterLen} theme={theme} />
        </group>
      );
    }

    case 'bathroom': {
      return (
        <group position={[cx, 0, cz]}>
          <BathroomSuite theme={theme} />
        </group>
      );
    }

    case 'balcony': {
      return (
        <group position={[cx, 0, cz]}>
          <BalconySet theme={theme} />
        </group>
      );
    }

    case 'lawn': {
      return (
        <group position={[cx, 0, cz]}>
          <LawnGardenSet theme={theme} />
        </group>
      );
    }

    case 'utility': {
      const isWashBalcony = (room.name || '').toLowerCase().includes('wash') || (room.name || '').toLowerCase().includes('laundry');
      if (!isWashBalcony) return null;
      return (
        <group position={[cx, 0, cz]}>
          <UtilitySet theme={theme} />
        </group>
      );
    }

    case 'parking':
      return null;

    default:
      return null;
  }
}
