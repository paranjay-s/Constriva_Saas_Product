// frontend/src/features/plan-viewer/builders/buildOpenings.ts
import * as THREE from 'three';
import type { PbrMaterialCatalog } from '../materials/materials';

export interface OpeningData {
  id: string;
  wallId: string;
  kind: 'door' | 'window' | 'slider' | 'arch';
  offset: number; // m from wall start to center
  width: number;
  height: number;
  sill: number;
}

export interface WallData {
  id: string;
  a: { x: number; y: number };
  b: { x: number; y: number };
  thickness: number;
  height: number;
  kind: 'exterior' | 'interior';
}

export interface ProximityDoorNode {
  id: string;
  group: THREE.Group;
  hingeGroup: THREE.Group;
  worldPos: THREE.Vector3;
  targetAngle: number;
  currentAngle: number;
}

export interface OpeningsResult {
  group: THREE.Group;
  doors: ProximityDoorNode[];
}

/**
 * Builds glazed windows with marble sills and proximity auto-swing timber panel doors
 */
export function buildOpeningMeshes(
  wall: WallData,
  openings: OpeningData[],
  mats: PbrMaterialCatalog,
  ext: number,
  wallGroup: THREE.Group
): OpeningsResult {
  const group = new THREE.Group();
  group.name = `Openings_${wall.id}`;
  const doors: ProximityDoorNode[] = [];

  const t = wall.thickness;
  const H = wall.height;

  for (const op of openings) {
    const w = op.width;
    const h = Math.min(op.height, H - 0.04);
    const sill = Math.max(op.sill, 0);
    const xCenter = ext + op.offset;
    const yCenter = sill + h / 2;

    if (op.kind === 'arch') {
      continue;
    }

    if (op.kind === 'window' || op.kind === 'slider') {
      const windowGroup = new THREE.Group();
      windowGroup.name = `Window_${op.id}`;

      const frameThick = 0.045;
      const frameDepth = Math.max(t + 0.02, 0.08);

      // Outer dark bronze frame
      // Left jamb
      const leftJambGeo = new THREE.BoxGeometry(frameThick, h, frameDepth);
      const leftJamb = new THREE.Mesh(leftJambGeo, mats.doorBronzeFrame);
      leftJamb.position.set(xCenter - w / 2 + frameThick / 2, yCenter, 0);
      leftJamb.castShadow = true;
      leftJamb.receiveShadow = true;
      windowGroup.add(leftJamb);

      // Right jamb
      const rightJambGeo = new THREE.BoxGeometry(frameThick, h, frameDepth);
      const rightJamb = new THREE.Mesh(rightJambGeo, mats.doorBronzeFrame);
      rightJamb.position.set(xCenter + w / 2 - frameThick / 2, yCenter, 0);
      rightJamb.castShadow = true;
      rightJamb.receiveShadow = true;
      windowGroup.add(rightJamb);

      // Top header
      const topHeadGeo = new THREE.BoxGeometry(w, frameThick, frameDepth);
      const topHead = new THREE.Mesh(topHeadGeo, mats.doorBronzeFrame);
      topHead.position.set(xCenter, sill + h - frameThick / 2, 0);
      topHead.castShadow = true;
      topHead.receiveShadow = true;
      windowGroup.add(topHead);

      // Bottom frame
      const botFrameGeo = new THREE.BoxGeometry(w, frameThick, frameDepth);
      const botFrame = new THREE.Mesh(botFrameGeo, mats.doorBronzeFrame);
      botFrame.position.set(xCenter, sill + frameThick / 2, 0);
      botFrame.castShadow = true;
      botFrame.receiveShadow = true;
      windowGroup.add(botFrame);

      // Polished Carrara marble window sill projecting 4cm into the room
      if (sill >= 0.2) {
        const sillGeo = new THREE.BoxGeometry(w + 0.08, 0.04, t + 0.08);
        const sillMesh = new THREE.Mesh(sillGeo, mats.carraraMarble);
        sillMesh.position.set(xCenter, sill - 0.018, 0);
        sillMesh.castShadow = true;
        sillMesh.receiveShadow = true;
        windowGroup.add(sillMesh);
      }

      // Physical glass pane with realistic transmission & reflections
      const glassW = Math.max(w - frameThick * 2, 0.1);
      const glassH = Math.max(h - frameThick * 2, 0.1);
      const glassGeo = new THREE.BoxGeometry(glassW, glassH, 0.016);
      const glassMesh = new THREE.Mesh(glassGeo, mats.architecturalGlass);
      glassMesh.position.set(xCenter, yCenter, 0);
      glassMesh.castShadow = false;
      glassMesh.receiveShadow = false;
      windowGroup.add(glassMesh);

      // Vertical mullions for sliders or wide windows
      const numPanels = Math.max(1, Math.round(w / 1.0));
      if (numPanels > 1) {
        const step = (w - frameThick * 2) / numPanels;
        for (let p = 1; p < numPanels; p++) {
          const mullionX = xCenter - w / 2 + frameThick + p * step;
          const mullionGeo = new THREE.BoxGeometry(0.03, glassH, 0.04);
          const mullion = new THREE.Mesh(mullionGeo, mats.doorBronzeFrame);
          mullion.position.set(mullionX, yCenter, 0);
          mullion.castShadow = true;
          mullion.receiveShadow = true;
          windowGroup.add(mullion);
        }
      }

      group.add(windowGroup);
    } else if (op.kind === 'door') {
      const doorGroup = new THREE.Group();
      doorGroup.name = `Door_${op.id}`;

      const liningThick = 0.035;
      const liningDepth = t + 0.015;

      // Dark bronze door frame lining
      const leftLiningGeo = new THREE.BoxGeometry(liningThick, h, liningDepth);
      const leftLining = new THREE.Mesh(leftLiningGeo, mats.doorBronzeFrame);
      leftLining.position.set(xCenter - w / 2 + liningThick / 2, h / 2, 0);
      leftLining.castShadow = true;
      doorGroup.add(leftLining);

      const rightLiningGeo = new THREE.BoxGeometry(liningThick, h, liningDepth);
      const rightLining = new THREE.Mesh(rightLiningGeo, mats.doorBronzeFrame);
      rightLining.position.set(xCenter + w / 2 - liningThick / 2, h / 2, 0);
      rightLining.castShadow = true;
      doorGroup.add(rightLining);

      const topLiningGeo = new THREE.BoxGeometry(w, liningThick, liningDepth);
      const topLining = new THREE.Mesh(topLiningGeo, mats.doorBronzeFrame);
      topLining.position.set(xCenter, h - liningThick / 2, 0);
      topLining.castShadow = true;
      doorGroup.add(topLining);

      // Proximity Auto-Swing Hinge Node
      const hingeGroup = new THREE.Group();
      hingeGroup.name = `Hinge_${op.id}`;
      hingeGroup.position.set(xCenter - w / 2 + liningThick, 0, 0);

      // Timber door leaf with recessed panel geometry
      const leafW = Math.max(w - liningThick * 2, 0.2);
      const leafH = Math.max(h - liningThick, 0.5);
      const leafThick = 0.04;

      const leafGeo = new THREE.BoxGeometry(leafW, leafH, leafThick);
      const leafMesh = new THREE.Mesh(leafGeo, mats.doorTimber);
      leafMesh.position.set(leafW / 2, leafH / 2, 0);
      leafMesh.castShadow = true;
      leafMesh.receiveShadow = true;
      hingeGroup.add(leafMesh);

      // Recessed panel detailing on both sides of door leaf
      const panelGeo = new THREE.BoxGeometry(leafW * 0.72, leafH * 0.76, 0.043);
      const panelMesh = new THREE.Mesh(panelGeo, mats.doorTimber);
      panelMesh.position.set(leafW / 2, leafH / 2, 0);
      hingeGroup.add(panelMesh);

      // Brushed brass lever handle & latch plate
      const handleGroup = new THREE.Group();
      handleGroup.position.set(leafW - 0.08, 0.98, 0);

      // Plate
      const plateGeo = new THREE.BoxGeometry(0.04, 0.16, 0.048);
      const plate = new THREE.Mesh(plateGeo, mats.brushedBrass);
      handleGroup.add(plate);

      // Lever handles front & back
      const leverGeo = new THREE.BoxGeometry(0.12, 0.018, 0.018);
      const leverFront = new THREE.Mesh(leverGeo, mats.brushedBrass);
      leverFront.position.set(0.04, 0, 0.035);
      handleGroup.add(leverFront);

      const leverBack = new THREE.Mesh(leverGeo, mats.brushedBrass);
      leverBack.position.set(0.04, 0, -0.035);
      handleGroup.add(leverBack);

      hingeGroup.add(handleGroup);
      doorGroup.add(hingeGroup);
      group.add(doorGroup);

      // Calculate door world position for proximity sensing
      const localDoorPos = new THREE.Vector3(xCenter, h / 2, 0);
      const worldDoorPos = localDoorPos.clone();
      wallGroup.localToWorld(worldDoorPos);

      doors.push({
        id: op.id,
        group: doorGroup,
        hingeGroup,
        worldPos: worldDoorPos,
        targetAngle: 0,
        currentAngle: 0,
      });
    }
  }

  return { group, doors };
}

/**
 * Updates proximity door auto-swing when visitor camera approaches within 2.5m
 */
export function updateProximityDoors(
  doors: ProximityDoorNode[],
  cameraPos: THREE.Vector3,
  delta = 0.016
): boolean {
  let isMoving = false;
  const speed = Math.min(1.0, delta * 6.5);

  for (const door of doors) {
    const dist = cameraPos.distanceTo(door.worldPos);

    // Open door if within 2.5m, close if visitor moves away (> 3.0m)
    if (dist < 2.5) {
      door.targetAngle = 1.32; // ~75 degrees open
    } else if (dist > 3.0) {
      door.targetAngle = 0.0; // fully closed
    }

    const diff = door.targetAngle - door.currentAngle;
    if (Math.abs(diff) > 0.005) {
      door.currentAngle += diff * speed;
      door.hingeGroup.rotation.y = door.currentAngle;
      isMoving = true;
    } else if (door.currentAngle !== door.targetAngle) {
      door.currentAngle = door.targetAngle;
      door.hingeGroup.rotation.y = door.currentAngle;
    }
  }

  return isMoving;
}
