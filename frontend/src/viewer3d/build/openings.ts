// build/openings.ts
import * as THREE from 'three';
import type { MaterialLibrary } from '../materials/materials';
import type { Opening, Wall } from '../types';

export function buildWallOpenings(
  wall: Wall,
  openings: Opening[],
  mats: MaterialLibrary,
  ext: number
): THREE.Group {
  const group = new THREE.Group();
  group.name = `Openings_${wall.id}`;

  const t = wall.thickness;
  const H = wall.height;

  for (const op of openings) {
    const w = op.width;
    const h = Math.min(op.height, H - 0.04);
    const sill = Math.max(op.sill, 0);
    const xCenter = ext + op.offset;
    const yCenter = sill + h / 2;

    if (op.kind === 'arch') {
      // Arches remain open geometric cutouts
      continue;
    }

    if (op.kind === 'window' || op.kind === 'slider') {
      const windowGroup = new THREE.Group();
      windowGroup.name = `Window_${op.id}`;

      const frameThick = 0.045;
      const frameDepth = Math.max(t + 0.02, 0.08);

      // Outer Frame
      // Left jamb
      const leftJambGeo = new THREE.BoxGeometry(frameThick, h, frameDepth);
      const leftJamb = new THREE.Mesh(leftJambGeo, mats.frame);
      leftJamb.position.set(xCenter - w / 2 + frameThick / 2, yCenter, 0);
      leftJamb.castShadow = true;
      leftJamb.receiveShadow = true;
      windowGroup.add(leftJamb);

      // Right jamb
      const rightJambGeo = new THREE.BoxGeometry(frameThick, h, frameDepth);
      const rightJamb = new THREE.Mesh(rightJambGeo, mats.frame);
      rightJamb.position.set(xCenter + w / 2 - frameThick / 2, yCenter, 0);
      rightJamb.castShadow = true;
      rightJamb.receiveShadow = true;
      windowGroup.add(rightJamb);

      // Top header
      const topHeadGeo = new THREE.BoxGeometry(w, frameThick, frameDepth);
      const topHead = new THREE.Mesh(topHeadGeo, mats.frame);
      topHead.position.set(xCenter, sill + h - frameThick / 2, 0);
      topHead.castShadow = true;
      topHead.receiveShadow = true;
      windowGroup.add(topHead);

      // Bottom sill frame
      const botFrameGeo = new THREE.BoxGeometry(w, frameThick, frameDepth);
      const botFrame = new THREE.Mesh(botFrameGeo, mats.frame);
      botFrame.position.set(xCenter, sill + frameThick / 2, 0);
      botFrame.castShadow = true;
      botFrame.receiveShadow = true;
      windowGroup.add(botFrame);

      // Ledge sill on windows above floor
      if (sill >= 0.3) {
        const ledgeGeo = new THREE.BoxGeometry(w + 0.08, 0.035, t + 0.07);
        const ledge = new THREE.Mesh(ledgeGeo, mats.stone);
        ledge.position.set(xCenter, sill - 0.015, 0);
        ledge.castShadow = true;
        ledge.receiveShadow = true;
        windowGroup.add(ledge);
      }

      // Translucent pale-blue Glass pane
      const glassW = Math.max(w - frameThick * 2, 0.1);
      const glassH = Math.max(h - frameThick * 2, 0.1);
      const glassGeo = new THREE.BoxGeometry(glassW, glassH, 0.015);
      const glassMesh = new THREE.Mesh(glassGeo, mats.glass);
      glassMesh.position.set(xCenter, yCenter, 0);
      glassMesh.castShadow = false;
      glassMesh.receiveShadow = false;
      windowGroup.add(glassMesh);

      // Vertical mullions for sliders or wide windows (every ~1.0m)
      const numPanels = Math.max(1, Math.round(w / 1.0));
      if (numPanels > 1) {
        const step = (w - frameThick * 2) / numPanels;
        for (let p = 1; p < numPanels; p++) {
          const mullionX = xCenter - w / 2 + frameThick + p * step;
          const mullionGeo = new THREE.BoxGeometry(0.03, glassH, 0.04);
          const mullion = new THREE.Mesh(mullionGeo, mats.frame);
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

      // Frame lining: left jamb, right jamb, top header
      const leftLiningGeo = new THREE.BoxGeometry(liningThick, h, liningDepth);
      const leftLining = new THREE.Mesh(leftLiningGeo, mats.frame);
      leftLining.position.set(xCenter - w / 2 + liningThick / 2, h / 2, 0);
      leftLining.castShadow = true;
      leftLining.receiveShadow = true;
      doorGroup.add(leftLining);

      const rightLiningGeo = new THREE.BoxGeometry(liningThick, h, liningDepth);
      const rightLining = new THREE.Mesh(rightLiningGeo, mats.frame);
      rightLining.position.set(xCenter + w / 2 - liningThick / 2, h / 2, 0);
      rightLining.castShadow = true;
      rightLining.receiveShadow = true;
      doorGroup.add(rightLining);

      const topLiningGeo = new THREE.BoxGeometry(w, liningThick, liningDepth);
      const topLining = new THREE.Mesh(topLiningGeo, mats.frame);
      topLining.position.set(xCenter, h - liningThick / 2, 0);
      topLining.castShadow = true;
      topLining.receiveShadow = true;
      doorGroup.add(topLining);

      // Open door leaf rotated ~70° at the hinge side
      const leafW = Math.max(w - liningThick * 2, 0.2);
      const leafH = Math.max(h - liningThick, 0.5);
      const leafThick = 0.04;

      const hingeGroup = new THREE.Group();
      hingeGroup.position.set(xCenter - w / 2 + liningThick, 0, 0);
      // Rotated ~70 degrees into room
      hingeGroup.rotation.y = 1.22;

      const leafGeo = new THREE.BoxGeometry(leafW, leafH, leafThick);
      const leafMesh = new THREE.Mesh(leafGeo, mats.woodFurniture);
      // Pivot leaf from its hinge edge
      leafMesh.position.set(leafW / 2, leafH / 2, 0);
      leafMesh.castShadow = true;
      leafMesh.receiveShadow = true;
      hingeGroup.add(leafMesh);

      // Door lever handle
      const handleGeo = new THREE.BoxGeometry(0.08, 0.02, 0.04);
      const handle = new THREE.Mesh(handleGeo, mats.stoolDark);
      handle.position.set(leafW - 0.07, 0.95, 0.035);
      handle.castShadow = true;
      hingeGroup.add(handle);

      doorGroup.add(hingeGroup);
      group.add(doorGroup);
    }
  }

  return group;
}

