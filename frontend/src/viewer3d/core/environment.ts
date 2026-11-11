// core/environment.ts
import * as THREE from 'three';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';

export interface EnvironmentContext {
  envTexture: THREE.Texture;
  dispose: () => void;
}

export function setupEnvironment(
  renderer: THREE.WebGLRenderer,
  scene: THREE.Scene
): EnvironmentContext {
  const pmremGenerator = new THREE.PMREMGenerator(renderer);
  pmremGenerator.compileEquirectangularShader();

  const roomEnv = new RoomEnvironment();
  const renderTarget = pmremGenerator.fromScene(roomEnv, 0.04);
  const envTexture = renderTarget.texture;

  scene.environment = envTexture;
  // Soft architectural reflections
  if ('environmentIntensity' in scene) {
    (scene as any).environmentIntensity = 0.4;
  }

  return {
    envTexture,
    dispose: () => {
      renderTarget.dispose();
      pmremGenerator.dispose();
      roomEnv.dispose();
    },
  };
}

