import type { MaterialTheme } from '../materials/materials';

interface RailingProps {
  start: [number, number];
  end: [number, number];
  height?: number;
  theme: MaterialTheme;
}

export function BalconyRailingMesh({
  start,
  end,
  height = 1.05,
  theme,
}: RailingProps) {
  const [x1, y1] = start;
  const [x2, y2] = end;
  const dx = x2 - x1;
  const dz = y2 - y1;
  const length = Math.sqrt(dx * dx + dz * dz);
  if (length <= 0.2) return null;

  const angle = -Math.atan2(dz, dx);
  const postSpacing = 1.2;
  const numPosts = Math.max(2, Math.floor(length / postSpacing) + 1);

  return (
    <group position={[x1, 0, y1]} rotation={[0, angle, 0]}>
      {/* Top Handrail */}
      <mesh position={[length / 2, height, 0]} castShadow>
        <boxGeometry args={[length, 0.04, 0.06]} />
        <meshStandardMaterial {...theme.railingMetal} />
      </mesh>

      {/* Bottom Base Channel */}
      <mesh position={[length / 2, 0.06, 0]} castShadow>
        <boxGeometry args={[length, 0.04, 0.05]} />
        <meshStandardMaterial {...theme.railingMetal} />
      </mesh>

      {/* Tempered Safety Glass Balustrade Infill */}
      <mesh position={[length / 2, height / 2 + 0.03, 0]}>
        <boxGeometry args={[length - 0.04, height - 0.1, 0.015]} />
        <meshStandardMaterial {...theme.railingGlass} />
      </mesh>

      {/* Vertical Stanchion Posts */}
      {Array.from({ length: numPosts }).map((_, i) => {
        const posX = (i / (numPosts - 1)) * length;
        return (
          <mesh key={i} position={[posX, height / 2, 0]} castShadow>
            <cylinderGeometry args={[0.018, 0.018, height, 12]} />
            <meshStandardMaterial {...theme.railingMetal} />
          </mesh>
        );
      })}
    </group>
  );
}
