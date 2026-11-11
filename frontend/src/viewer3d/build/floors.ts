// build/floors.ts
import * as THREE from 'three';
import type { Plan, RoomType } from '../types';
import type { MaterialLibrary } from '../materials/materials';

export interface FloorsResult {
  group: THREE.Group;
  roomMeshes: Map<string, THREE.Mesh>;
  updateHighlight: (tag: string | null) => void;
  selectRoom: (roomId: string | null) => void;
}

export function buildFloors(plan: Plan, mats: MaterialLibrary): FloorsResult {
  const group = new THREE.Group();
  group.name = 'RoomFloors';
  const roomMeshes = new Map<string, THREE.Mesh>();

  const getFloorMaterial = (type: RoomType): THREE.Material => {
    switch (type) {
      case 'bedroom':
        return mats.floorBedroom;
      case 'living':
      case 'drawing':
      case 'dining':
      case 'kitchen':
      case 'passage':
      case 'store':
      case 'utility':
        return mats.floorLiving;
      case 'toilet':
      case 'wash':
        return mats.floorBath;
      case 'puja':
        return mats.floorPuja;
      case 'parking':
      case 'stairs':
        return mats.floorConcrete;
      case 'balcony':
      case 'terrace':
        return mats.floorDeck;
      default:
        return mats.floorLiving;
    }
  };

  for (const r of plan.rooms) {
    if (r.polygon.length < 3) continue;

    const shape = new THREE.Shape();
    // In plan: x is X, y is Y (depth).
    // Using y = -p.y and then geometry.rotateX(-Math.PI / 2) places plan-Y onto world +Z with normal pointing up (+Y)
    shape.moveTo(r.polygon[0].x, -r.polygon[0].y);
    for (let i = 1; i < r.polygon.length; i++) {
      shape.lineTo(r.polygon[i].x, -r.polygon[i].y);
    }
    shape.closePath();

    const geometry = new THREE.ShapeGeometry(shape);
    geometry.rotateX(-Math.PI / 2);

    // Compute custom world-space UVs so plank texture is continuous across all rooms
    const posAttr = geometry.attributes.position;
    const uvs = new Float32Array(posAttr.count * 2);
    for (let i = 0; i < posAttr.count; i++) {
      const wx = posAttr.getX(i);
      const wz = posAttr.getZ(i);
      uvs[i * 2] = wx;
      uvs[i * 2 + 1] = wz;
    }
    geometry.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));

    const defaultMat = getFloorMaterial(r.type);
    const mesh = new THREE.Mesh(geometry, defaultMat);
    mesh.name = `Floor_${r.id}`;
    // Lift +0.001 m over plinth to avoid z-fighting
    mesh.position.set(0, 0.001, 0);
    mesh.receiveShadow = true;
    mesh.castShadow = false;

    // Attach room metadata for raycasting / selection
    mesh.userData = {
      roomId: r.id,
      roomType: r.type,
      defaultMaterial: defaultMat,
    };

    group.add(mesh);
    roomMeshes.set(r.id, mesh);
  }

  const updateHighlight = (tag: string | null) => {
    const t = (tag || '').toLowerCase().trim();

    roomMeshes.forEach((mesh) => {
      const rType: RoomType = mesh.userData.roomType;
      const defMat = mesh.userData.defaultMaterial;

      if (!t) {
        mesh.material = defMat;
        return;
      }

      // Tiles / Flooring highlight
      if (t.includes('tile') || t.includes('floor') || t.includes('skirting') || t === 'marble') {
        // Enclosed indoor rooms receive tile highlighting
        if (
          rType === 'living' ||
          rType === 'drawing' ||
          rType === 'dining' ||
          rType === 'bedroom' ||
          rType === 'kitchen' ||
          rType === 'toilet' ||
          rType === 'puja'
        ) {
          mesh.material = mats.highlightTiles;
          return;
        }
      }

      // Ballast / Foundation highlight
      if (t.includes('ballast') || t.includes('coarse_aggregate')) {
        mesh.material = mats.highlightBallast;
        return;
      }

      mesh.material = defMat;
    });
  };

  const selectRoom = (selectedId: string | null) => {
    roomMeshes.forEach((mesh, id) => {
      if (id === selectedId) {
        // Subtle room focus tint
        (mesh.material as any).emissive = new THREE.Color(0x332211);
        (mesh.material as any).emissiveIntensity = 0.25;
      } else {
        if ((mesh.material as any).emissive) {
          (mesh.material as any).emissive = new THREE.Color(0x000000);
          (mesh.material as any).emissiveIntensity = 0.0;
        }
      }
    });
  };

  return {
    group,
    roomMeshes,
    updateHighlight,
    selectRoom,
  };
}
