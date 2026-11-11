// build/walls.ts
import * as THREE from 'three';
import type { Opening, Plan, Wall } from '../types';
import type { MaterialLibrary } from '../materials/materials';
import { distance } from '../utils/geometry';
import { buildWallOpenings } from './openings';

export interface ExteriorWallNode {
  group: THREE.Group;
  bodyMesh: THREE.Mesh;
  capMesh: THREE.Mesh;
  wall: Wall;
  normal: THREE.Vector2; // outward normal
  baseHeight: number;
}

export interface WallsResult {
  group: THREE.Group;
  exteriorWalls: ExteriorWallNode[];
  interiorWallGroup: THREE.Group;
  wallMeshes: THREE.Mesh[];
  updateHighlight: (tag: string | null) => void;
}

export function buildWalls(
  plan: Plan,
  mats: MaterialLibrary,
  buildingCenter: THREE.Vector3 = new THREE.Vector3(0, 0, 0)
): WallsResult {
  const group = new THREE.Group();
  group.name = 'AllWalls';

  const exteriorWallGroup = new THREE.Group();
  exteriorWallGroup.name = 'ExteriorWalls';
  group.add(exteriorWallGroup);

  const interiorWallGroup = new THREE.Group();
  interiorWallGroup.name = 'InteriorWalls';
  group.add(interiorWallGroup);

  const exteriorWalls: ExteriorWallNode[] = [];
  const wallMeshes: THREE.Mesh[] = [];

  // Group openings by wall ID
  const openingsByWall = new Map<string, Opening[]>();
  for (const op of plan.openings) {
    if (!openingsByWall.has(op.wallId)) openingsByWall.set(op.wallId, []);
    openingsByWall.get(op.wallId)!.push(op);
  }

  for (let idx = 0; idx < plan.walls.length; idx++) {
    const w = plan.walls[idx];
    const isExterior = w.kind === 'exterior';
    const t = w.thickness;
    const H = w.height;
    const rawLen = distance(w.a, w.b);
    if (rawLen < 0.05) continue;

    // Direction vector of wall
    const dx = (w.b.x - w.a.x) / rawLen;
    const dy = (w.b.y - w.a.y) / rawLen;

    // Corner extension to seal T-junctions and corner miters cleanly
    const ext = t / 2;
    const len = rawLen + ext * 2;

    // Gather and validate openings for this wall
    const rawOps = openingsByWall.get(w.id) || [];
    const validOps: Opening[] = [];

    // Filter out overlapping openings and clamp inside wall boundaries
    for (const op of rawOps) {
      const opW = op.width;
      const opH = Math.min(op.height, H - 0.04);
      const minCenter = opW / 2 + 0.05;
      const maxCenter = len - opW / 2 - 0.05;
      let center = ext + op.offset;

      if (center < minCenter || center > maxCenter) {
        center = Math.max(minCenter, Math.min(maxCenter, center));
      }

      // Check overlap with already accepted openings
      const left = center - opW / 2;
      const right = center + opW / 2;
      const overlaps = validOps.some((v) => {
        const vCenter = ext + v.offset;
        const vLeft = vCenter - v.width / 2;
        const vRight = vCenter + v.width / 2;
        return left < vRight && right > vLeft;
      });

      if (!overlaps && opW < len - 0.1) {
        validOps.push({
          ...op,
          offset: center - ext,
          width: opW,
          height: opH,
        });
      }
    }

    // Build extruded wall shape with opening holes
    const shape = new THREE.Shape();
    shape.moveTo(0, 0);
    shape.lineTo(len, 0);
    shape.lineTo(len, H);
    shape.lineTo(0, H);
    shape.closePath();

    for (const op of validOps) {
      const x0 = ext + op.offset - op.width / 2;
      const x1 = x0 + op.width;
      // Holes must not touch the boundary outline (0.01m sill margin, 0.02m top margin)
      const y0 = Math.max(op.sill, 0.01);
      const y1 = Math.min(op.sill + op.height, H - 0.02);

      if (x1 > x0 + 0.05 && y1 > y0 + 0.05) {
        const hole = new THREE.Path();
        hole.moveTo(x0, y0);
        hole.lineTo(x1, y0);
        hole.lineTo(x1, y1);
        hole.lineTo(x0, y1);
        hole.closePath();
        shape.holes.push(hole);
      }
    }

    const geo = new THREE.ExtrudeGeometry(shape, {
      depth: t,
      bevelEnabled: false,
    });
    // Center wall thickness on the wall line
    geo.translate(0, 0, -t / 2);

    const bodyMesh = new THREE.Mesh(geo, mats.wallFace);
    bodyMesh.name = `WallBody_${w.id}`;
    bodyMesh.castShadow = true;
    bodyMesh.receiveShadow = true;

    // Signature top cap:
    // Exterior: capH 0.08, capExtra 0.06, color wallCapExterior (#35363A, dark charcoal outline)
    // Interior: capH 0.03, capExtra 0.02, color wallCapInterior (#F2F0EB)
    const capH = isExterior ? 0.08 : 0.03;
    const capExtra = isExterior ? 0.06 : 0.02;
    const capMat = isExterior ? mats.wallCapExterior : mats.wallCapInterior;

    const capGeo = new THREE.BoxGeometry(len + 0.005, capH, t + capExtra);
    const capMesh = new THREE.Mesh(capGeo, capMat);
    capMesh.name = `WallCap_${w.id}`;
    capMesh.castShadow = true;
    capMesh.receiveShadow = true;

    // Position cap on top of the wall with micro-offset to prevent z-fighting at corners
    const zFightOffset = (idx % 10) * 0.0005;
    capMesh.position.set(len / 2, H + capH / 2 + zFightOffset, 0);

    const wallGroup = new THREE.Group();
    wallGroup.name = `WallGroup_${w.id}`;
    wallGroup.add(bodyMesh);
    wallGroup.add(capMesh);

    // Add glazed windows, sliders, and open doors with leaves
    const openingsGroup = buildWallOpenings(w, validOps, mats, ext);
    wallGroup.add(openingsGroup);

    // Position wall at start endpoint with corner extension
    wallGroup.position.set(w.a.x - dx * ext, 0, w.a.y - dy * ext);
    // Rotate: plan-Y maps to Three.js world-Z
    wallGroup.rotation.y = -Math.atan2(w.b.y - w.a.y, w.b.x - w.a.x);

    wallMeshes.push(bodyMesh);

    if (isExterior) {
      // Calculate outward normal facing away from building centroid
      const midX = (w.a.x + w.b.x) / 2;
      const midY = (w.a.y + w.b.y) / 2;

      // Normal perpendicular to wall
      const nx = -dy;
      const ny = dx;

      // Vector from building center to wall mid
      const toMidX = midX - buildingCenter.x;
      const toMidY = midY - buildingCenter.z;

      // Ensure normal points outward
      const dot = nx * toMidX + ny * toMidY;
      const outX = dot >= 0 ? nx : -nx;
      const outY = dot >= 0 ? ny : -ny;

      const normal = new THREE.Vector2(outX, outY).normalize();

      exteriorWalls.push({
        group: wallGroup,
        bodyMesh,
        capMesh,
        wall: w,
        normal,
        baseHeight: H,
      });

      exteriorWallGroup.add(wallGroup);
    } else {
      interiorWallGroup.add(wallGroup);
    }
  }

  const updateHighlight = (tag: string | null) => {
    const t = (tag || '').toLowerCase().trim();

    wallMeshes.forEach((mesh) => {
      if (!t) {
        mesh.material = mats.wallFace;
        return;
      }

      // Brick / Masonry
      if (t.includes('brick') || t.includes('masonry') || t.includes('aac')) {
        mesh.material = mats.highlightBrick;
        return;
      }

      // Steel / Rebar embedded in structural walls
      if (t.includes('steel') || t.includes('rebar') || t.includes('reinforcement')) {
        mesh.material = mats.highlightSteel;
        return;
      }

      // Plaster / Paint on walls
      if (t.includes('plaster') || t.includes('paint')) {
        mesh.material = mats.highlightPlaster;
        return;
      }

      // Cement / Mortar in wall construction
      if (t.includes('cement') || t.includes('mortar') || t.includes('binder')) {
        mesh.material = mats.highlightCement;
        return;
      }

      // Sand / Mortar
      if (t.includes('sand') || t.includes('fine_aggregate')) {
        mesh.material = mats.highlightSand;
        return;
      }

      mesh.material = mats.wallFace;
    });
  };

  return {
    group,
    exteriorWalls,
    interiorWallGroup,
    wallMeshes,
    updateHighlight,
  };
}
