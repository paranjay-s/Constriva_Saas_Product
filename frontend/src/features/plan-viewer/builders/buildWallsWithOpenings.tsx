// frontend/src/features/plan-viewer/builders/buildWallsWithOpenings.tsx
import * as THREE from 'three';
import {
  getPbrMaterialCatalog,
  type PbrMaterialCatalog,
} from '../materials/materials';
import {
  buildOpeningMeshes,
  type OpeningData,
  type ProximityDoorNode,
  type WallData,
} from './buildOpenings';

export interface SlicedWallNode {
  group: THREE.Group;
  bodyMeshes: THREE.Mesh[];
  capMesh?: THREE.Mesh;
  wall: WallData;
  normal: THREE.Vector2; // outward normal
  baseHeight: number;
}

export interface WallsConstructionResult {
  group: THREE.Group;
  walls: SlicedWallNode[];
  doors: ProximityDoorNode[];
  updateHighlight: (tag: string | null) => void;
  setConstructionPhase: (phase: number) => void; // 4D timeline support: 0 (foundation) to 1 (full walls)
}

function distance(a: { x: number; y: number }, b: { x: number; y: number }): number {
  return Math.hypot(b.x - a.x, b.y - a.y);
}

/**
 * Builds sliced architectural walls with sill walls, lintel beams, skirting baseboards & crown mouldings
 */
export function buildWallsWithOpenings(
  wallsData: WallData[],
  openingsData: OpeningData[],
  mats: PbrMaterialCatalog = getPbrMaterialCatalog(),
  buildingCenter: THREE.Vector3 = new THREE.Vector3(0, 0, 0)
): WallsConstructionResult {
  const group = new THREE.Group();
  group.name = 'StructuralWallsGroup';

  const walls: SlicedWallNode[] = [];
  const allDoors: ProximityDoorNode[] = [];
  const allWallMeshes: THREE.Mesh[] = [];

  // Group openings by wall ID
  const openingsByWall = new Map<string, OpeningData[]>();
  for (const op of openingsData) {
    if (!openingsByWall.has(op.wallId)) openingsByWall.set(op.wallId, []);
    openingsByWall.get(op.wallId)!.push(op);
  }

  for (let idx = 0; idx < wallsData.length; idx++) {
    const w = wallsData[idx];
    const isExterior = w.kind === 'exterior';
    const t = w.thickness;
    const H = w.height;
    const rawLen = distance(w.a, w.b);
    if (rawLen < 0.05) continue;

    const dx = (w.b.x - w.a.x) / rawLen;
    const dy = (w.b.y - w.a.y) / rawLen;

    const ext = t / 2;
    const len = rawLen + ext * 2;

    const wallGroup = new THREE.Group();
    wallGroup.name = `Wall_${w.id}`;

    // Position wall at start endpoint with corner extension
    wallGroup.position.set(w.a.x - dx * ext, 0, w.a.y - dy * ext);
    wallGroup.rotation.y = -Math.atan2(w.b.y - w.a.y, w.b.x - w.a.x);

    // Wall material: Sand stucco for exterior, Silk eggshell plaster for interior
    const wallMat = isExterior ? mats.sandStucco : mats.interiorPlaster;

    // Sort valid openings along wall length
    const rawOps = openingsByWall.get(w.id) || [];
    const validOps: OpeningData[] = [];

    for (const op of rawOps) {
      const opW = op.width;
      const opH = Math.min(op.height, H - 0.04);
      const center = ext + op.offset;
      if (center - opW / 2 >= 0.05 && center + opW / 2 <= len - 0.05) {
        validOps.push({ ...op, offset: op.offset, width: opW, height: opH });
      }
    }
    validOps.sort((a, b) => a.offset - b.offset);

    const bodyMeshes: THREE.Mesh[] = [];

    // Slice wall into segments:
    // 1. Full-height wall piers between openings
    // 2. Window sill segments (0m to sill)
    // 3. Lintel header beams (sill + height to H)
    let currentX = 0;

    for (const op of validOps) {
      const opLeft = ext + op.offset - op.width / 2;
      const opRight = ext + op.offset + op.width / 2;
      const sill = Math.max(op.sill, 0);
      const head = sill + op.height;

      // Pier before opening
      if (opLeft > currentX + 0.02) {
        const pierW = opLeft - currentX;
        const pierGeo = new THREE.BoxGeometry(pierW, H, t);
        const pier = new THREE.Mesh(pierGeo, wallMat);
        pier.position.set(currentX + pierW / 2, H / 2, 0);
        pier.castShadow = true;
        pier.receiveShadow = true;
        wallGroup.add(pier);
        bodyMeshes.push(pier);
        allWallMeshes.push(pier);
      }

      // Window sill masonry under opening (if window)
      if (sill > 0.05) {
        const sillGeo = new THREE.BoxGeometry(op.width, sill, t);
        const sillMesh = new THREE.Mesh(sillGeo, wallMat);
        sillMesh.position.set(ext + op.offset, sill / 2, 0);
        sillMesh.castShadow = true;
        sillMesh.receiveShadow = true;
        wallGroup.add(sillMesh);
        bodyMeshes.push(sillMesh);
        allWallMeshes.push(sillMesh);
      }

      // Lintel / header beam above opening
      if (H > head + 0.05) {
        const lintelH = H - head;
        const lintelGeo = new THREE.BoxGeometry(op.width, lintelH, t);
        const lintelMesh = new THREE.Mesh(lintelGeo, wallMat);
        lintelMesh.position.set(ext + op.offset, head + lintelH / 2, 0);
        lintelMesh.castShadow = true;
        lintelMesh.receiveShadow = true;
        wallGroup.add(lintelMesh);
        bodyMeshes.push(lintelMesh);
        allWallMeshes.push(lintelMesh);
      }

      currentX = opRight;
    }

    // Final pier after last opening
    if (len > currentX + 0.02) {
      const pierW = len - currentX;
      const pierGeo = new THREE.BoxGeometry(pierW, H, t);
      const pier = new THREE.Mesh(pierGeo, wallMat);
      pier.position.set(currentX + pierW / 2, H / 2, 0);
      pier.castShadow = true;
      pier.receiveShadow = true;
      wallGroup.add(pier);
      bodyMeshes.push(pier);
      allWallMeshes.push(pier);
    }

    // Continuous 10cm Skirting Baseboard along interior wall footings
    if (!isExterior) {
      const skirtingH = 0.1;
      const skirtingThick = t + 0.024;
      const skirtingGeo = new THREE.BoxGeometry(len, skirtingH, skirtingThick);
      const skirting = new THREE.Mesh(skirtingGeo, mats.skirtingBaseboard);
      skirting.position.set(len / 2, skirtingH / 2, 0);
      skirting.castShadow = true;
      wallGroup.add(skirting);
    }

    // Ceiling Crown Moulding profile along top wall joint
    const crownH = 0.06;
    const crownThick = t + 0.02;
    const crownGeo = new THREE.BoxGeometry(len, crownH, crownThick);
    const crown = new THREE.Mesh(crownGeo, mats.crownMoulding);
    crown.position.set(len / 2, H - crownH / 2, 0);
    crown.castShadow = true;
    wallGroup.add(crown);

    // Signature Dark Parapet Cap on exterior walls
    let capMesh: THREE.Mesh | undefined;
    if (isExterior) {
      const capH = 0.08;
      const capExtra = 0.06;
      const capGeo = new THREE.BoxGeometry(len + 0.01, capH, t + capExtra);
      capMesh = new THREE.Mesh(capGeo, mats.exteriorWallCap);
      capMesh.position.set(len / 2, H + capH / 2, 0);
      capMesh.castShadow = true;
      capMesh.receiveShadow = true;
      wallGroup.add(capMesh);
    }

    // Build Glazed Openings & Proximity Auto-Swing Doors
    const openingsRes = buildOpeningMeshes(w, validOps, mats, ext, wallGroup);
    wallGroup.add(openingsRes.group);
    allDoors.push(...openingsRes.doors);

    // Compute outward normal for cutaway
    const midX = (w.a.x + w.b.x) / 2;
    const midY = (w.a.y + w.b.y) / 2;
    const nx = -dy;
    const ny = dx;
    const toMidX = midX - buildingCenter.x;
    const toMidY = midY - buildingCenter.z;
    const dot = nx * toMidX + ny * toMidY;
    const outX = dot >= 0 ? nx : -nx;
    const outY = dot >= 0 ? ny : -ny;
    const normal = new THREE.Vector2(outX, outY).normalize();

    walls.push({
      group: wallGroup,
      bodyMeshes,
      capMesh,
      wall: w,
      normal,
      baseHeight: H,
    });

    group.add(wallGroup);
  }

  // Material highlighting for BOQ verification
  const updateHighlight = (tag: string | null) => {
    const t = (tag || '').toLowerCase().trim();

    allWallMeshes.forEach((mesh) => {
      if (!t) {
        mesh.material = mats.sandStucco;
        return;
      }
      if (t.includes('brick') || t.includes('masonry') || t.includes('aac')) {
        mesh.material = new THREE.MeshStandardMaterial({
          color: 0xe05638,
          roughness: 0.65,
        });
        return;
      }
      if (t.includes('steel') || t.includes('rebar')) {
        mesh.material = new THREE.MeshStandardMaterial({
          color: 0x06b6d4,
          metalness: 0.8,
          roughness: 0.2,
        });
        return;
      }
      if (t.includes('cement') || t.includes('mortar')) {
        mesh.material = new THREE.MeshStandardMaterial({
          color: 0xa855f7,
          roughness: 0.7,
        });
        return;
      }
      if (t.includes('sand')) {
        mesh.material = new THREE.MeshStandardMaterial({
          color: 0xf59e0b,
          roughness: 0.85,
        });
        return;
      }
      if (t.includes('plaster') || t.includes('paint')) {
        mesh.material = new THREE.MeshStandardMaterial({
          color: 0xfb7185,
          roughness: 0.75,
        });
        return;
      }
      mesh.material = mats.sandStucco;
    });
  };

  // 4D timeline animation support (0 = columns/framing only, 1 = full walls)
  const setConstructionPhase = (phase: number) => {
    const clamped = Math.max(0, Math.min(1, phase));
    walls.forEach((wNode) => {
      wNode.group.scale.y = clamped;
      wNode.group.visible = clamped > 0.05;
    });
  };

  return {
    group,
    walls,
    doors: allDoors,
    updateHighlight,
    setConstructionPhase,
  };
}

