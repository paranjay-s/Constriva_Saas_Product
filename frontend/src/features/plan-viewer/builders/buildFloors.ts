// frontend/src/features/plan-viewer/builders/buildFloors.ts
import * as THREE from 'three';
import {
  getPbrMaterialCatalog,
  type PbrMaterialCatalog,
} from '../materials/materials';

export interface RoomData {
  id: string;
  name?: string;
  type?: string;
  kind?: string;
  polygon: { x: number; y: number }[];
}

export interface FloorsConstructionResult {
  group: THREE.Group;
  plinthGroup: THREE.Group;
  ceilingGroup: THREE.Group;
  roomMeshes: Map<string, THREE.Mesh>;
  updateHighlight: (tag: string | null) => void;
  selectRoom: (roomId: string | null) => void;
  updateCeilingVisibility: (cameraY: number) => void;
  setConstructionPhase: (phase: number) => void; // 4D timeline support
}

/**
 * Builds elevated plinth foundation, entrance steps, multi-zone PBR floors & auto-culling smart ceilings
 */
export function buildFloorsWithPbr(
  rooms: RoomData[],
  mats: PbrMaterialCatalog = getPbrMaterialCatalog(),
  _onRoomSelect?: (roomId: string) => void
): FloorsConstructionResult {
  const group = new THREE.Group();
  group.name = 'AllFloorsGroup';

  const plinthGroup = new THREE.Group();
  plinthGroup.name = 'PlinthGroup';
  group.add(plinthGroup);

  const roomFloorsGroup = new THREE.Group();
  roomFloorsGroup.name = 'RoomFloors';
  group.add(roomFloorsGroup);

  const ceilingGroup = new THREE.Group();
  ceilingGroup.name = 'CeilingGroup';
  ceilingGroup.visible = false; // Hidden by default in orbit view
  group.add(ceilingGroup);

  const roomMeshes = new Map<string, THREE.Mesh>();

  // Compute building footprint bounding box
  let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
  for (const r of rooms) {
    for (const pt of r.polygon) {
      if (pt.x < minX) minX = pt.x;
      if (pt.x > maxX) maxX = pt.x;
      if (pt.y < minZ) minZ = pt.y;
      if (pt.y > maxZ) maxZ = pt.y;
    }
  }

  if (minX === Infinity || !isFinite(minX)) {
    minX = -6;
    maxX = 6;
    minZ = -6;
    maxZ = 6;
  }

  const footW = maxX - minX;
  const footD = maxZ - minZ;
  const centerX = (minX + maxX) / 2;
  const centerZ = (minZ + maxZ) / 2;

  // 1. Elevated Plinth Slab (0.45m height, projecting 0.25m around footprint)
  const plinthH = 0.45;
  const plinthGeo = new THREE.BoxGeometry(footW + 0.5, plinthH, footD + 0.5);
  const plinthMat = new THREE.MeshStandardMaterial({
    color: 0xe2ddd5,
    roughness: 0.82,
    metalness: 0.02,
  });
  const plinthMesh = new THREE.Mesh(plinthGeo, plinthMat);
  plinthMesh.position.set(centerX, -plinthH / 2, centerZ);
  plinthMesh.receiveShadow = true;
  plinthGroup.add(plinthMesh);

  // Cantilevered Front Entrance Steps (2 steps: 15cm riser, 30cm tread)
  const stepW = 2.4;
  const stepMat = mats.carraraMarble;

  const step1Geo = new THREE.BoxGeometry(stepW, 0.15, 0.6);
  const step1 = new THREE.Mesh(step1Geo, stepMat);
  step1.position.set(centerX, -0.375, maxZ + 0.25 + 0.3);
  step1.receiveShadow = true;
  plinthGroup.add(step1);

  const step2Geo = new THREE.BoxGeometry(stepW - 0.2, 0.15, 0.3);
  const step2 = new THREE.Mesh(step2Geo, stepMat);
  step2.position.set(centerX, -0.225, maxZ + 0.25 + 0.15);
  step2.receiveShadow = true;
  plinthGroup.add(step2);

  // Surrounding 3D Lawn Grass plane (ground level at y = -plinthH)
  const lawnGeo = new THREE.PlaneGeometry(footW + 28, footD + 28);
  lawnGeo.rotateX(-Math.PI / 2);
  const lawnMesh = new THREE.Mesh(lawnGeo, mats.lawnGrass);
  lawnMesh.position.set(centerX, -plinthH - 0.01, centerZ);
  lawnMesh.receiveShadow = true;
  plinthGroup.add(lawnMesh);

  // 2. Multi-Zone Room Floors & Smart Ceilings
  for (const r of rooms) {
    if (r.polygon.length < 3) continue;

    const kind = (r.kind || '').toLowerCase();
    const type = (r.type || '').toLowerCase();
    const name = (r.name || r.id).toLowerCase();

    // Skip punching solid floor for open vertical ventilation shafts
    if (kind === 'void' || name.includes('shaft') || name.includes('void')) {
      continue;
    }

    // Determine PBR Floor Material
    let floorMat: THREE.Material = mats.carraraMarble;
    if (type.includes('bed') || name.includes('bed')) {
      floorMat = mats.herringboneOak;
    } else if (
      type.includes('bath') ||
      type.includes('toilet') ||
      name.includes('bath') ||
      name.includes('toilet') ||
      name.includes('wc') ||
      type.includes('kitchen') ||
      name.includes('kitchen') ||
      type.includes('wash') ||
      name.includes('wash')
    ) {
      floorMat = mats.ceramicTile;
    } else if (
      type.includes('balcony') ||
      type.includes('terrace') ||
      type.includes('deck') ||
      type.includes('patio') ||
      type.includes('verandah') ||
      type.includes('sitout') ||
      name.includes('balcony') ||
      name.includes('terrace') ||
      name.includes('deck') ||
      name.includes('patio') ||
      name.includes('verandah') ||
      name.includes('sitout')
    ) {
      floorMat = mats.teakDeck;
    } else if (type.includes('parking') || name.includes('parking') || name.includes('garage')) {
      floorMat = mats.sandStucco;
    } else if (kind === 'outdoor' || name.includes('lawn')) {
      floorMat = mats.lawnGrass;
    }

    // Extrude Room Shape
    const shape = new THREE.Shape();
    // Invert Y so plan-Y maps to Three.js +Z
    shape.moveTo(r.polygon[0].x, -r.polygon[0].y);
    for (let i = 1; i < r.polygon.length; i++) {
      shape.lineTo(r.polygon[i].x, -r.polygon[i].y);
    }
    shape.closePath();

    const floorGeo = new THREE.ShapeGeometry(shape);
    floorGeo.rotateX(-Math.PI / 2);

    const floorMesh = new THREE.Mesh(floorGeo, floorMat);
    floorMesh.position.set(0, 0.002, 0); // Micro lift above plinth
    floorMesh.receiveShadow = true;
    floorMesh.name = `Floor_${r.id}`;

    // Click to select/teleport room
    floorMesh.userData = { roomId: r.id, roomName: r.name || r.id };
    roomMeshes.set(r.id, floorMesh);
    roomFloorsGroup.add(floorMesh);

    // 3. Smart Ceiling with Recessed LED Cove Lighting
    if (kind !== 'outdoor' && !type.includes('balcony') && !name.includes('open')) {
      const ceilingH = 2.85;
      const ceilingGeo = new THREE.ShapeGeometry(shape);
      ceilingGeo.rotateX(Math.PI / 2); // Normal pointing down into room

      const ceilingMesh = new THREE.Mesh(ceilingGeo, mats.ceilingPlaster);
      ceilingMesh.position.set(0, ceilingH, 0);
      ceilingGroup.add(ceilingMesh);

      // Recessed LED cove perimeter light strip along room edge
      const coveShape = new THREE.Shape();
      coveShape.moveTo(r.polygon[0].x, -r.polygon[0].y);
      for (let i = 1; i < r.polygon.length; i++) {
        coveShape.lineTo(r.polygon[i].x, -r.polygon[i].y);
      }
      coveShape.closePath();

      const edgePts = shape.getPoints();
      const lineGeo = new THREE.BufferGeometry().setFromPoints(
        edgePts.map((p) => new THREE.Vector3(p.x, ceilingH - 0.05, -p.y))
      );
      const coveLine = new THREE.Line(
        lineGeo,
        new THREE.LineBasicMaterial({ color: 0xffe6a3, linewidth: 2 })
      );
      ceilingGroup.add(coveLine);
    }
  }

  // Update ceiling visibility based on camera altitude
  const updateCeilingVisibility = (cameraY: number) => {
    // Hide ceiling in Orbit / High-Angle mode (> 3.0m)
    // Show solid ceiling with glowing cove lighting in Room Walkthrough mode (<= 2.3m)
    ceilingGroup.visible = cameraY <= 2.3;
  };

  const updateHighlight = (tag: string | null) => {
    const t = (tag || '').toLowerCase().trim();

    roomMeshes.forEach((mesh) => {
      if (!t) {
        mesh.material = (mesh as any).originalMaterial || mesh.material;
        return;
      }

      if (t.includes('tile') || t.includes('flooring')) {
        mesh.material = new THREE.MeshStandardMaterial({
          color: 0x10b981,
          roughness: 0.3,
          emissive: new THREE.Color(0x059669),
          emissiveIntensity: 0.2,
        });
        return;
      }
      if (t.includes('marble')) {
        mesh.material = new THREE.MeshStandardMaterial({
          color: 0x38bdf8,
          roughness: 0.2,
        });
        return;
      }
      if (t.includes('wood')) {
        mesh.material = new THREE.MeshStandardMaterial({
          color: 0xd97706,
          roughness: 0.4,
        });
        return;
      }

      mesh.material = (mesh as any).originalMaterial || mesh.material;
    });
  };

  const selectRoom = (roomId: string | null) => {
    roomMeshes.forEach((mesh, id) => {
      if (roomId && id === roomId) {
        mesh.material = new THREE.MeshStandardMaterial({
          color: 0x60a5fa,
          roughness: 0.3,
          emissive: new THREE.Color(0x2563eb),
          emissiveIntensity: 0.15,
        });
      } else {
        mesh.material = (mesh as any).originalMaterial || mesh.material;
      }
    });
  };

  // 4D timeline animation support (0 = ground slab only, 1 = complete finishes)
  const setConstructionPhase = (phase: number) => {
    const clamped = Math.max(0, Math.min(1, phase));
    plinthGroup.visible = clamped >= 0.05;
    roomFloorsGroup.visible = clamped >= 0.35;
    ceilingGroup.visible = clamped >= 0.85;
  };

  return {
    group,
    plinthGroup,
    ceilingGroup,
    roomMeshes,
    updateHighlight,
    selectRoom,
    updateCeilingVisibility,
    setConstructionPhase,
  };
}
