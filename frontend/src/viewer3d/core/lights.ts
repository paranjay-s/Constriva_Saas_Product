// core/lights.ts
import * as THREE from 'three';

export interface LightsContext {
  group: THREE.Group;
  sunLight: THREE.DirectionalLight;
  hemiLight: THREE.HemisphereLight;
  fillLight: THREE.DirectionalLight;
  updateBounds: (radius: number, center: THREE.Vector3) => void;
  dispose: () => void;
}

export function createLights(): LightsContext {
  const group = new THREE.Group();
  group.name = 'LightsGroup';

  // Ambient hemisphere daylight
  const hemiLight = new THREE.HemisphereLight(0xffffff, 0xe9e2d6, 1.05);
  hemiLight.position.set(0, 50, 0);
  group.add(hemiLight);

  // Key sun light: warm sunlight from upper-left-front direction (-0.6, 1.0, 0.5)
  const sunLight = new THREE.DirectionalLight(0xfff4e0, 2.9);
  sunLight.castShadow = true;
  sunLight.shadow.mapSize.width = 4096;
  sunLight.shadow.mapSize.height = 4096;
  sunLight.shadow.bias = -0.0004;
  sunLight.shadow.normalBias = 0.03;
  group.add(sunLight);

  // Soft cool sky fill light from opposite side
  const fillLight = new THREE.DirectionalLight(0xdfe8ff, 0.55);
  fillLight.castShadow = false;
  group.add(fillLight);

  const updateBounds = (radius: number, center: THREE.Vector3) => {
    const dist = Math.max(radius * 2.5, 20);

    // Sun positioned along (-0.6, 1.0, 0.5) direction
    sunLight.position.set(
      center.x - 0.6 * dist,
      center.y + 1.0 * dist,
      center.z + 0.5 * dist
    );
    sunLight.target.position.copy(center);
    if (!sunLight.target.parent) group.add(sunLight.target);

    // Orthographic shadow camera bounds sized to bounding sphere * 1.2
    const d = radius * 1.25;
    sunLight.shadow.camera.left = -d;
    sunLight.shadow.camera.right = d;
    sunLight.shadow.camera.top = d;
    sunLight.shadow.camera.bottom = -d;
    sunLight.shadow.camera.near = 1.0;
    sunLight.shadow.camera.far = dist * 2.8;
    sunLight.shadow.camera.updateProjectionMatrix();

    // Fill light from opposite side (0.6, 0.6, -0.5)
    fillLight.position.set(
      center.x + 0.6 * dist,
      center.y + 0.6 * dist,
      center.z - 0.5 * dist
    );
    fillLight.target.position.copy(center);
    if (!fillLight.target.parent) group.add(fillLight.target);
  };

  return {
    group,
    sunLight,
    hemiLight,
    fillLight,
    updateBounds,
    dispose: () => {
      sunLight.dispose();
      fillLight.dispose();
      hemiLight.dispose();
    },
  };
}

