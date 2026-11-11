import { useMemo } from 'react';
import type { Wall, Opening } from '../../../types';
import type { MaterialTheme } from '../materials/materials';

interface WallOpeningProps {
  wall: Wall;
  openings: Opening[];
  wallHeight: number;
  theme: MaterialTheme;
  isExterior: boolean;
  isHighlighted?: boolean;
  highlightColor?: string;
  highlightEmissive?: string;
}

export function WallWithOpeningsMesh({
  wall,
  openings,
  wallHeight,
  theme,
  isExterior,
  isHighlighted,
  highlightColor,
  highlightEmissive,
}: WallOpeningProps) {
  const [x1, y1] = wall.start;
  const [x2, y2] = wall.end;
  const dx = x2 - x1;
  const dz = y2 - y1;
  const wallLen = Math.sqrt(dx * dx + dz * dz);
  const angle = -Math.atan2(dz, dx);
  const thickness = wall.thickness || (isExterior ? 0.25 : 0.15);

  // Filter openings for this wall and sort by offset
  const wallOpenings = useMemo(() => {
    return (openings || [])
      .filter((op) => op.wall_id === wall.id)
      .sort((a, b) => a.offset - b.offset);
  }, [openings, wall.id]);

  // Generate solid wall blocks & opening elements
  const { wallSegments, doorElements, windowElements } = useMemo(() => {
    const segments: Array<{
      centerOffset: number;
      length: number;
      yBottom: number;
      height: number;
    }> = [];

    const doors: Array<{
      centerOffset: number;
      width: number;
      height: number;
      offset: number;
    }> = [];

    const windows: Array<{
      centerOffset: number;
      width: number;
      sill: number;
      height: number;
    }> = [];

    let currentPos = 0;

    for (const op of wallOpenings) {
      const opStart = Math.max(0, Math.min(op.offset, wallLen));
      const opEnd = Math.max(opStart, Math.min(op.offset + op.width, wallLen));
      const opWidth = opEnd - opStart;

      if (opWidth <= 0.05) continue;

      // Solid wall segment prior to this opening
      if (opStart > currentPos + 0.02) {
        const segLen = opStart - currentPos;
        segments.push({
          centerOffset: currentPos + segLen / 2,
          length: segLen,
          yBottom: 0,
          height: wallHeight,
        });
      }

      const opMid = opStart + opWidth / 2;

      if (op.type === 'door') {
        const doorH = Math.min(op.height || 2.1, wallHeight);
        doors.push({
          centerOffset: opMid,
          width: opWidth,
          height: doorH,
          offset: opStart,
        });

        // Header wall segment above the door if wall is taller than door
        if (wallHeight > doorH + 0.05) {
          segments.push({
            centerOffset: opMid,
            length: opWidth,
            yBottom: doorH,
            height: wallHeight - doorH,
          });
        }
      } else if (op.type === 'window') {
        const sill = Math.min(op.sill ?? 0.9, wallHeight);
        const winH = Math.min(op.height || 1.3, Math.max(0, wallHeight - sill));

        windows.push({
          centerOffset: opMid,
          width: opWidth,
          sill: sill,
          height: winH,
        });

        // Sill wall segment below the window
        if (sill > 0.05) {
          segments.push({
            centerOffset: opMid,
            length: opWidth,
            yBottom: 0,
            height: sill,
          });
        }

        // Header wall segment above window if wall is taller than sill + winH
        const winTop = sill + winH;
        if (wallHeight > winTop + 0.05) {
          segments.push({
            centerOffset: opMid,
            length: opWidth,
            yBottom: winTop,
            height: wallHeight - winTop,
          });
        }
      }

      currentPos = opEnd;
    }

    // Final wall segment from last opening to wall end
    if (currentPos < wallLen - 0.02) {
      const segLen = wallLen - currentPos;
      segments.push({
        centerOffset: currentPos + segLen / 2,
        length: segLen,
        yBottom: 0,
        height: wallHeight,
      });
    }

    // If wall had no openings at all, single continuous segment
    if (wallOpenings.length === 0) {
      segments.push({
        centerOffset: wallLen / 2,
        length: wallLen,
        yBottom: 0,
        height: wallHeight,
      });
    }

    return { wallSegments: segments, doorElements: doors, windowElements: windows };
  }, [wallOpenings, wallLen, wallHeight]);

  const wallMatParams = isExterior ? theme.wallPlasterExt : theme.wallPlaster;
  const wallColor = isHighlighted ? (highlightColor || '#E05638') : wallMatParams.color;
  const emissive = isHighlighted ? (highlightEmissive || highlightColor || '#C2410C') : '#000000';
  const emissiveIntensity = isHighlighted ? 0.65 : 0;

  return (
    <group position={[x1, 0, y1]} rotation={[0, angle, 0]}>
      {/* Solid Wall Segments */}
      {wallSegments.map((seg, idx) => (
        <mesh
          key={`wseg_${idx}`}
          position={[seg.centerOffset, seg.yBottom + seg.height / 2, 0]}
          castShadow
          receiveShadow
        >
          <boxGeometry args={[seg.length, seg.height, thickness]} />
          <meshStandardMaterial
            color={wallColor}
            roughness={wallMatParams.roughness}
            metalness={wallMatParams.metalness}
            emissive={emissive}
            emissiveIntensity={emissiveIntensity}
          />
        </mesh>
      ))}

      {/* Architectural Wall Top Coping Cap for Razor-Sharp Layout Outlines */}
      {wallSegments.map((seg, idx) => (
        <mesh
          key={`wcap_${idx}`}
          position={[seg.centerOffset, seg.yBottom + seg.height + 0.012, 0]}
          castShadow
        >
          <boxGeometry args={[seg.length + 0.008, 0.024, thickness + 0.012]} />
          <meshStandardMaterial
            color="#2D3036"
            roughness={0.35}
            metalness={0.2}
          />
        </mesh>
      ))}

      {/* Skirting / Baseboards on internal faces */}
      {!isExterior && (
        <group position={[wallLen / 2, 0.04, 0]}>
          <mesh position={[0, 0, thickness / 2 + 0.005]}>
            <boxGeometry args={[wallLen, 0.08, 0.01]} />
            <meshStandardMaterial color="#EAE6DE" roughness={0.5} />
          </mesh>
          <mesh position={[0, 0, -thickness / 2 - 0.005]}>
            <boxGeometry args={[wallLen, 0.08, 0.01]} />
            <meshStandardMaterial color="#EAE6DE" roughness={0.5} />
          </mesh>
        </group>
      )}

      {/* Door Openings: Frame + Swung Panel */}
      {doorElements.map((d, idx) => {
        const frameThickness = 0.045;
        const panelWidth = d.width - frameThickness * 2;
        const panelHeight = d.height - frameThickness;

        return (
          <group key={`door_${idx}`} position={[d.centerOffset, 0, 0]}>
            {/* Door Frame Left Jamb */}
            <mesh position={[-d.width / 2 + frameThickness / 2, d.height / 2, 0]} castShadow>
              <boxGeometry args={[frameThickness, d.height, thickness + 0.01]} />
              <meshStandardMaterial {...theme.doorFrame} />
            </mesh>

            {/* Door Frame Right Jamb */}
            <mesh position={[d.width / 2 - frameThickness / 2, d.height / 2, 0]} castShadow>
              <boxGeometry args={[frameThickness, d.height, thickness + 0.01]} />
              <meshStandardMaterial {...theme.doorFrame} />
            </mesh>

            {/* Door Frame Top Lintel */}
            <mesh position={[0, d.height - frameThickness / 2, 0]} castShadow>
              <boxGeometry args={[d.width, frameThickness, thickness + 0.01]} />
              <meshStandardMaterial {...theme.doorFrame} />
            </mesh>

            {/* Door Leaf (Swung at 45° angle) */}
            <group position={[-panelWidth / 2, 0, 0]} rotation={[0, -Math.PI / 4, 0]}>
              <mesh position={[panelWidth / 2, panelHeight / 2, 0.02]} castShadow>
                <boxGeometry args={[panelWidth, panelHeight, 0.04]} />
                <meshStandardMaterial {...theme.doorWood} />
              </mesh>

              {/* Architectural Brass Lever Handle */}
              <group position={[panelWidth * 0.88, panelHeight * 0.48, 0.04]}>
                <mesh rotation={[0, 0, Math.PI / 2]}>
                  <cylinderGeometry args={[0.012, 0.012, 0.1, 8]} />
                  <meshStandardMaterial color="#D4AF37" roughness={0.25} metalness={0.85} />
                </mesh>
              </group>
            </group>

            {/* Door Sill Threshold */}
            <mesh position={[0, 0.01, 0]}>
              <boxGeometry args={[d.width, 0.02, thickness + 0.02]} />
              <meshStandardMaterial color="#3A3836" roughness={0.7} />
            </mesh>
          </group>
        );
      })}

      {/* Window Openings: Architectural Frame + Double Glazing */}
      {windowElements.map((w, idx) => {
        const frameW = 0.05;
        const frameDepth = thickness * 0.65;
        const innerW = w.width - frameW * 2;
        const innerH = w.height - frameW * 2;
        const centerY = w.sill + w.height / 2;

        return (
          <group key={`win_${idx}`} position={[w.centerOffset, centerY, 0]}>
            {/* Outer Frame Perimeter */}
            {/* Left Frame */}
            <mesh position={[-w.width / 2 + frameW / 2, 0, 0]} castShadow>
              <boxGeometry args={[frameW, w.height, frameDepth]} />
              <meshStandardMaterial {...theme.windowFrame} />
            </mesh>

            {/* Right Frame */}
            <mesh position={[w.width / 2 - frameW / 2, 0, 0]} castShadow>
              <boxGeometry args={[frameW, w.height, frameDepth]} />
              <meshStandardMaterial {...theme.windowFrame} />
            </mesh>

            {/* Top Frame */}
            <mesh position={[0, w.height / 2 - frameW / 2, 0]} castShadow>
              <boxGeometry args={[w.width, frameW, frameDepth]} />
              <meshStandardMaterial {...theme.windowFrame} />
            </mesh>

            {/* Bottom Sill Frame */}
            <mesh position={[0, -w.height / 2 + frameW / 2, 0]} castShadow>
              <boxGeometry args={[w.width, frameW, frameDepth]} />
              <meshStandardMaterial {...theme.windowFrame} />
            </mesh>

            {/* Center Vertical Mullion Divider */}
            {w.width > 1.2 && (
              <mesh position={[0, 0, 0]} castShadow>
                <boxGeometry args={[0.035, innerH, frameDepth * 0.9]} />
                <meshStandardMaterial {...theme.windowFrame} />
              </mesh>
            )}

            {/* Low-E Architectural Glass Pane */}
            <mesh position={[0, 0, 0]}>
              <boxGeometry args={[innerW, innerH, 0.015]} />
              <meshStandardMaterial {...theme.windowGlass} />
            </mesh>

            {/* External Window Sill Ledge */}
            <mesh position={[0, -w.height / 2, thickness / 2 + 0.04]}>
              <boxGeometry args={[w.width + 0.1, 0.04, 0.09]} />
              <meshStandardMaterial color="#D8D4CC" roughness={0.6} />
            </mesh>
          </group>
        );
      })}
    </group>
  );
}
