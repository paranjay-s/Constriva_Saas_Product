// utils/dispose.ts
import * as THREE from 'three';

/**
 * Recursively disposes all objects, geometries, materials and textures in a scene or hierarchy.
 */
export function deepDispose(root: THREE.Object3D): void {
  root.traverse((obj) => {
    if ((obj as THREE.Mesh).isMesh || (obj as THREE.Line).isLine) {
      const mesh = obj as THREE.Mesh;
      if (mesh.geometry) {
        mesh.geometry.dispose();
      }

      if (mesh.material) {
        if (Array.isArray(mesh.material)) {
          mesh.material.forEach(disposeMaterial);
        } else {
          disposeMaterial(mesh.material);
        }
      }
    }
  });

  while (root.children.length > 0) {
    const child = root.children[0];
    root.remove(child);
  }
}

export function disposeMaterial(mat: THREE.Material): void {
  const m = mat as any;
  // Dispose all possible map textures on the material
  const textureKeys = [
    'map',
    'lightMap',
    'bumpMap',
    'normalMap',
    'specularMap',
    'envMap',
    'alphaMap',
    'roughnessMap',
    'metalnessMap',
    'emissiveMap',
    'clearcoatMap',
    'clearcoatRoughnessMap',
    'clearcoatNormalMap',
    'transmissionMap',
    'thicknessMap',
  ];

  for (const k of textureKeys) {
    if (m[k] && typeof m[k].dispose === 'function') {
      m[k].dispose();
    }
  }

  mat.dispose();
}

