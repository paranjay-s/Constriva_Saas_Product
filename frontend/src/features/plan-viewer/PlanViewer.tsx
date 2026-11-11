import { Suspense, useMemo, useRef, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Html } from '@react-three/drei';
import * as THREE from 'three';
import { useProject } from '../../context/ProjectContext';
import {
  IconBox,
  IconRefresh,
} from '../../components/ui/Icons';
import type { Room, Wall } from '../../types';
import {
  REALISTIC_THEME,
  CLAY_THEME,
  categorizeRoom,
  getRoomFloorMaterialParams,
  type MaterialTheme,
} from './materials/materials';
import { WallWithOpeningsMesh } from './builders/buildWallsWithOpenings';
import { BalconyRailingMesh } from './builders/buildRailings';
import { RoomFurnisher } from './furniture/roomFurnisher';
import { ensureCompleteWalls, filterValidRooms } from './builders/wallSynthesizer';

// Clean OrbitControls wrapper
function CameraRig({
  target,
  autoRotate,
  controlsRef,
}: {
  target: [number, number, number];
  autoRotate: boolean;
  controlsRef: React.RefObject<any>;
}) {
  return (
    <OrbitControls
      ref={controlsRef}
      makeDefault
      target={target}
      autoRotate={autoRotate}
      autoRotateSpeed={0.8}
      minDistance={3}
      maxDistance={45}
      maxPolarAngle={Math.PI / 2.05} // Do not dip below ground
      minPolarAngle={0.1}
      dampingFactor={0.08}
    />
  );
}

// Room Floor & HTML Label Component
function RoomFloor({
  room,
  theme,
  isSelected,
  isHighlighted,
  isDimmed,
  labelMode,
  onSelect,
}: {
  room: Room;
  theme: MaterialTheme;
  isSelected: boolean;
  isHighlighted: boolean;
  isDimmed: boolean;
  labelMode: 'smart' | 'all' | 'off';
  onSelect: () => void;
}) {
  const [isHovered, setIsHovered] = useState(false);
  const polygon = room.polygon || [];

  const { shape, borderPoints, cx, cz, width, depth, area } = useMemo(() => {
    const s = new THREE.Shape();
    if (polygon.length === 0) {
      return { shape: s, borderPoints: [], cx: 0, cz: 0, width: 0, depth: 0, area: 0 };
    }

    let minX = Infinity;
    let maxX = -Infinity;
    let minZ = Infinity;
    let maxZ = -Infinity;

    s.moveTo(polygon[0][0], polygon[0][1]);
    for (let i = 1; i < polygon.length; i++) {
      s.lineTo(polygon[i][0], polygon[i][1]);
    }
    s.closePath();

    for (const [x, z] of polygon) {
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (z < minZ) minZ = z;
      if (z > maxZ) maxZ = z;
    }

    const w = Math.round((maxX - minX) * 10) / 10;
    const d = Math.round((maxZ - minZ) * 10) / 10;

    // Shoelace formula for polygon area
    let shoelace = 0;
    for (let i = 0; i < polygon.length; i++) {
      const j = (i + 1) % polygon.length;
      shoelace += polygon[i][0] * polygon[j][1];
      shoelace -= polygon[j][0] * polygon[i][1];
    }
    const a = Math.round(Math.abs(shoelace / 2) * 10) / 10;

    const bPts = polygon.map(([x, z]) => new THREE.Vector3(x, 0.025, z));
    if (polygon.length > 0) {
      bPts.push(new THREE.Vector3(polygon[0][0], 0.025, polygon[0][1]));
    }

    return {
      shape: s,
      borderPoints: bPts,
      cx: minX + (maxX - minX) / 2,
      cz: minZ + (maxZ - minZ) / 2,
      width: w,
      depth: d,
      area: a,
    };
  }, [polygon]);

  const category = useMemo(() => categorizeRoom(room.name, room.id), [room.name, room.id]);
  const floorParams = useMemo(() => getRoomFloorMaterialParams(category, theme), [category, theme]);

  // Unit / Zone detection for clear visual differentiation
  const unitTag = useMemo(() => {
    const id = (room.id || '').toLowerCase();
    const name = (room.name || '').toLowerCase();
    if (id.includes('flat1') || name.includes('flat 1') || name.includes('flat-1')) return 'Flat 1';
    if (id.includes('flat2') || name.includes('flat 2') || name.includes('flat-2')) return 'Flat 2';
    if (name.includes('lawn') || name.includes('verandah') || name.includes('stair')) return 'Entrance';
    return null;
  }, [room.id, room.name]);

  // Subtle unit color tinting so Flat 1 and Flat 2 have unique personality
  const resolvedColor = useMemo(() => {
    if (isHighlighted) return '#D4B58A';
    if (isSelected) return '#E8D5BC';
    if (isHovered) return '#DFCEB7';
    if (unitTag === 'Flat 2' && (category === 'bedroom' || category === 'living')) {
      return '#B8874E';
    }
    return floorParams.color;
  }, [isHighlighted, isSelected, isHovered, unitTag, category, floorParams.color]);

  const emissive = isHighlighted || isSelected ? '#C5A77B' : isHovered ? '#8A6A3E' : '#000000';
  const emissiveIntensity = isHighlighted ? 0.45 : isSelected ? 0.3 : isHovered ? 0.15 : 0;
  const opacity = isDimmed ? 0.5 : 1.0;

  // Small utility room detection (toilets, ducts, shafts, wash)
  const isSmallRoom = area < 4.5 || category === 'bathroom' || category === 'utility' || category === 'void';
  const showExpanded = labelMode === 'all' || isSelected || isHovered;

  return (
    <group>
      {/* Floor Slab Mesh */}
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, 0.02, 0]}
        receiveShadow
        onClick={(e) => {
          e.stopPropagation();
          onSelect();
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setIsHovered(true);
        }}
        onPointerOut={() => setIsHovered(false)}
      >
        <shapeGeometry args={[shape]} />
        <meshStandardMaterial
          color={resolvedColor}
          roughness={floorParams.roughness}
          metalness={floorParams.metalness}
          emissive={emissive}
          emissiveIntensity={emissiveIntensity}
          transparent={isDimmed}
          opacity={opacity}
          side={THREE.DoubleSide}
        />
      </mesh>

      {/* Razor-sharp Perimeter Joint Border Line */}
      {borderPoints.length > 2 && (
        <lineLoop>
          <bufferGeometry
            attach="geometry"
            onUpdate={(geo) => geo.setFromPoints(borderPoints)}
          />
          <lineBasicMaterial
            attach="material"
            color={isSelected ? '#C5A77B' : isHovered ? '#947547' : '#5E564C'}
            linewidth={isSelected ? 2 : 1}
          />
        </lineLoop>
      )}

      {/* Non-congested Smart Floating Room Label */}
      {labelMode !== 'off' && (
        <Html
          position={[cx, 1.35, cz]}
          center
          distanceFactor={18}
          className="pointer-events-auto select-none"
        >
          <div
            onClick={(e) => {
              e.stopPropagation();
              onSelect();
            }}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
            className={`transition-all duration-200 cursor-pointer ${
              isSelected
                ? 'scale-110 shadow-lg'
                : isHovered
                ? 'scale-105 shadow-md'
                : 'shadow-sm'
            }`}
          >
            {isSmallRoom && !showExpanded ? (
              // Compact micro-pill for small spaces (Zero congestion!)
              <div
                className={`px-1.5 py-0.5 rounded-full text-[9px] font-bold tracking-tight border transition-colors ${
                  category === 'bathroom'
                    ? 'bg-sky-50/90 text-sky-800 border-sky-300'
                    : category === 'void'
                    ? 'bg-slate-100/90 text-slate-600 border-slate-300'
                    : 'bg-white/90 text-[#333] border-[#DDD8CE]'
                }`}
                title={`${room.name || 'Room'} • Click to focus`}
              >
                {category === 'bathroom' ? 'TOI' : category === 'void' ? 'OPEN' : (room.name || 'RM').slice(0, 4).toUpperCase()}
              </div>
            ) : (
              // Clean, elegant primary room badge
              <div
                className={`px-2.5 py-1 rounded-lg border text-center transition-all ${
                  isSelected
                    ? 'bg-[#1A1918] text-[#FFFFFF] border-[#C5A77B] ring-2 ring-[#C5A77B]/40'
                    : isHovered
                    ? 'bg-[#FFFFFF] text-[#111] border-[#C5A77B]'
                    : 'bg-white/92 backdrop-blur-md text-[#1A1918] border-[#DDD8CE]'
                }`}
              >
                <div className="flex items-center justify-center gap-1.5">
                  {unitTag && (
                    <span
                      className={`text-[8px] font-bold px-1 rounded uppercase tracking-wider ${
                        unitTag === 'Flat 1'
                          ? 'bg-amber-100 text-amber-800'
                          : unitTag === 'Flat 2'
                          ? 'bg-teal-100 text-teal-800'
                          : 'bg-emerald-100 text-emerald-800'
                      }`}
                    >
                      {unitTag}
                    </span>
                  )}
                  <span className="text-[10px] font-bold tracking-wide uppercase font-sans whitespace-nowrap">
                    {room.name || 'Room'}
                  </span>
                </div>
                {showExpanded && (
                  <div className={`text-[9px] mt-0.5 font-mono whitespace-nowrap ${isSelected ? 'text-[#C5A77B]' : 'text-[#706C64]'}`}>
                    {((room as any).dimensions)
                      ? `${(room as any).dimensions} • ${area} m²`
                      : `${width}m × ${depth}m • ${area} m²`}
                  </div>
                )}
              </div>
            )}
          </div>
        </Html>
      )}
    </group>
  );
}

// Complete 3D Architectural Scene
function ArchitecturalScene({
  isCutaway,
  isClay,
  labelMode,
  showFurniture,
  autoRotate,
  controlsRef,
}: {
  isCutaway: boolean;
  isClay: boolean;
  labelMode: 'smart' | 'all' | 'off';
  showFurniture: boolean;
  autoRotate: boolean;
  controlsRef: React.RefObject<any>;
}) {
  const { planData, selectedMaterialTag, activeRoomId, setActiveRoomId } = useProject();

  const theme = isClay ? CLAY_THEME : REALISTIC_THEME;
  const wallHeight = isCutaway ? 1.35 : 2.8;

  const level = planData.levels?.[0] || { walls: [], rooms: [], openings: [] };
  const rawWalls = level.walls || [];
  const rawRooms = level.rooms || [];
  const openings = level.openings || [];
  const columns = (level as any).columns || [];

  // 1. Filter out stray out-of-bounds rooms so rogue slabs never float behind the house
  const rooms = useMemo(() => filterValidRooms(rawRooms, rawWalls), [rawRooms, rawWalls]);

  // 2. Synthesize complete interior walls if missing, guaranteeing dividing walls are always rendered
  const walls = useMemo(() => ensureCompleteWalls(rawWalls, rooms), [rawWalls, rooms]);

  // Calculate building bounding box to ground foundation slab & center camera
  const { minX, maxX, minZ, maxZ, cx, cz, totalW, totalD } = useMemo(() => {
    let x0 = Infinity;
    let x1 = -Infinity;
    let z0 = Infinity;
    let z1 = -Infinity;

    for (const w of walls) {
      x0 = Math.min(x0, w.start[0], w.end[0]);
      x1 = Math.max(x1, w.start[0], w.end[0]);
      z0 = Math.min(z0, w.start[1], w.end[1]);
      z1 = Math.max(z1, w.start[1], w.end[1]);
    }

    if (x0 === Infinity) {
      x0 = 0;
      x1 = 10.5;
      z0 = 0;
      z1 = 8.5;
    }

    const w = x1 - x0;
    const d = z1 - z0;
    return {
      minX: x0,
      maxX: x1,
      minZ: z0,
      maxZ: z1,
      cx: x0 + w / 2,
      cz: z0 + d / 2,
      totalW: w,
      totalD: d,
    };
  }, [walls]);

  // Compute camera target based on activeRoomId or building center
  const cameraTarget: [number, number, number] = useMemo(() => {
    if (!activeRoomId) return [cx, 0.4, cz];
    const room = rooms.find((r) => r.id === activeRoomId);
    if (!room || !room.polygon?.length) return [cx, 0.4, cz];

    let sumX = 0;
    let sumZ = 0;
    for (const [x, z] of room.polygon) {
      sumX += x;
      sumZ += z;
    }
    return [sumX / room.polygon.length, 0.4, sumZ / room.polygon.length];
  }, [activeRoomId, rooms, cx, cz]);

  // Exterior wall identification (walls that touch the outer bounding box)
  const isWallExt = (wall: Wall) => {
    const eps = 0.3;
    const touchesMinX = Math.abs(wall.start[0] - minX) < eps && Math.abs(wall.end[0] - minX) < eps;
    const touchesMaxX = Math.abs(wall.start[0] - maxX) < eps && Math.abs(wall.end[0] - maxX) < eps;
    const touchesMinZ = Math.abs(wall.start[1] - minZ) < eps && Math.abs(wall.end[1] - minZ) < eps;
    const touchesMaxZ = Math.abs(wall.start[1] - maxZ) < eps && Math.abs(wall.end[1] - maxZ) < eps;
    return touchesMinX || touchesMaxX || touchesMinZ || touchesMaxZ;
  };

  return (
    <>
      <CameraRig target={cameraTarget} autoRotate={autoRotate} controlsRef={controlsRef} />

      {/* Clean Architectural Studio Neutral Grey Backdrop */}
      <color attach="background" args={['#DFE3E8']} />

      {/* Soft Architectural Daylight Lighting System */}
      <ambientLight intensity={0.85} color="#FFFFFF" />
      <hemisphereLight args={['#EDF2F7', '#D5DBE2', 0.65]} />

      {/* Directional Sunlight from Upper Left */}
      <directionalLight
        position={[cx - 12, 22, cz - 10]}
        intensity={1.7}
        color="#FFFBF2"
        castShadow
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
      />

      {/* Secondary Soft Cool Fill */}
      <directionalLight
        position={[cx + 14, 15, cz + 12]}
        intensity={0.5}
        color="#E4ECF4"
      />

      {/* Crisp Architectural White Foundation Plinth Slab */}
      <mesh position={[cx, -0.06, cz]} receiveShadow castShadow>
        <boxGeometry args={[totalW + 0.35, 0.12, totalD + 0.35]} />
        <meshStandardMaterial {...theme.foundationSlab} />
      </mesh>

      {/* Soft Contact Ambient Occlusion Shadow */}
      <mesh position={[cx, -0.121, cz]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[totalW + 2.2, totalD + 2.2]} />
        <meshBasicMaterial color="#CBD1D8" />
      </mesh>

      {/* Architectural Walls with True Openings */}
      <group>
        {walls.map((wall) => {
          const isHighlighted =
            selectedMaterialTag === 'paint' || selectedMaterialTag === 'concrete';

          return (
            <WallWithOpeningsMesh
              key={wall.id}
              wall={wall}
              openings={openings}
              wallHeight={wallHeight}
              theme={theme}
              isExterior={isWallExt(wall)}
              isHighlighted={isHighlighted}
            />
          );
        })}
      </group>

      {/* Structural RCC Columns with Chamfered Corners */}
      <group>
        {columns.map((col: any) => (
          <mesh
            key={col.id}
            position={[col.position[0], wallHeight / 2, col.position[1]]}
            castShadow
            receiveShadow
          >
            <boxGeometry args={[col.width || 0.23, wallHeight, col.depth || 0.23]} />
            <meshStandardMaterial
              color="#2B2D31"
              roughness={0.4}
              metalness={0.15}
            />
          </mesh>
        ))}
      </group>

      {/* Room Floors & Distinct Architectural Materials */}
      <group>
        {rooms.map((room) => {
          const isSelected = activeRoomId === room.id;
          const isDimmed = activeRoomId !== null && !isSelected;

          let isHighlighted = false;
          const cat = categorizeRoom(room.name, room.id);
          if (selectedMaterialTag === 'wood' && (cat === 'bedroom' || cat === 'living')) {
            isHighlighted = true;
          } else if (selectedMaterialTag === 'marble' && (cat === 'bathroom' || cat === 'living')) {
            isHighlighted = true;
          } else if (selectedMaterialTag === 'tiles' && (cat === 'kitchen' || cat === 'balcony')) {
            isHighlighted = true;
          }

          return (
            <RoomFloor
              key={room.id}
              room={room}
              theme={theme}
              isSelected={isSelected}
              isHighlighted={isHighlighted}
              isDimmed={isDimmed}
              labelMode={labelMode}
              onSelect={() => {
                setActiveRoomId(activeRoomId === room.id ? null : room.id);
              }}
            />
          );
        })}
      </group>

      {/* Balcony Railings along Terrace Edges */}
      <group>
        {rooms
          .filter((r) => categorizeRoom(r.name, r.id) === 'balcony')
          .map((balconyRoom) => {
            const poly = balconyRoom.polygon || [];
            let bMinX = Infinity;
            let bMaxX = -Infinity;
            let bMinZ = Infinity;
            let bMaxZ = -Infinity;
            for (const [x, z] of poly) {
              if (x < bMinX) bMinX = x;
              if (x > bMaxX) bMaxX = x;
              if (z < bMinZ) bMinZ = z;
              if (z > bMaxZ) bMaxZ = z;
            }
            return (
              <group key={`balcony_railings_${balconyRoom.id}`}>
                {/* Outer East edge */}
                <BalconyRailingMesh
                  start={[bMaxX, bMinZ]}
                  end={[bMaxX, bMaxZ]}
                  height={isCutaway ? 1.05 : 1.15}
                  theme={theme}
                />
                {/* Outer North edge */}
                <BalconyRailingMesh
                  start={[bMaxX, bMaxZ]}
                  end={[bMinX, bMaxZ]}
                  height={isCutaway ? 1.05 : 1.15}
                  theme={theme}
                />
              </group>
            );
          })}
      </group>

      {/* Procedural Scaled Interior Furniture */}
      {showFurniture && (
        <group>
          {rooms.map((room) => {
            const isDimmed = activeRoomId !== null && activeRoomId !== room.id;
            return (
              <group key={`furniture_${room.id}`} visible={!isDimmed || isCutaway}>
                <RoomFurnisher room={room} theme={theme} />
              </group>
            );
          })}
        </group>
      )}
    </>
  );
}

export function PlanViewer() {
  const { planData, activeRoomId, setActiveRoomId, selectedMaterialTag, setSelectedMaterialTag } =
    useProject();

  const [isCutaway, setIsCutaway] = useState(true);
  const [isClay, setIsClay] = useState(false);
  const [labelMode, setLabelMode] = useState<'smart' | 'all' | 'off'>('smart');
  const [showFurniture, setShowFurniture] = useState(true);
  const [autoRotate, setAutoRotate] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const controlsRef = useRef<any>(null);

  const level = planData.levels?.[0] || { walls: [], rooms: [] };
  const rooms = level.rooms || [];

  // Reset Camera to front entrance architectural isometric overview
  const handleResetCamera = () => {
    setActiveRoomId(null);
    if (controlsRef.current) {
      controlsRef.current.target.set(5.56, 0.4, 8.38);
      controlsRef.current.object.position.set(11.6, 15, 22.4);
      controlsRef.current.update();
    }
  };

  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  };

  // Find currently selected room details
  const activeRoom = useMemo(() => {
    if (!activeRoomId) return null;
    return rooms.find((r) => r.id === activeRoomId) || null;
  }, [activeRoomId, rooms]);

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full min-h-[560px] bg-[#DFE3E8] overflow-hidden rounded-xl border border-[#CBD2D9] select-none shadow-sm"
    >
      {/* Three.js Canvas */}
      <Canvas
        shadows
        camera={{ position: [11.6, 15, 22.4], fov: 34, near: 0.1, far: 120 }}
        className="w-full h-full cursor-grab active:cursor-grabbing"
      >
        <Suspense
          fallback={
            <Html center>
              <div className="flex items-center gap-2 p-3 rounded-lg bg-white shadow text-xs text-[#555]">
                <span className="w-3 h-3 rounded-full border-2 border-[#C5A77B] border-t-transparent animate-spin" />
                <span>Loading 3D Studio...</span>
              </div>
            </Html>
          }
        >
          <ArchitecturalScene
            isCutaway={isCutaway}
            isClay={isClay}
            labelMode={labelMode}
            showFurniture={showFurniture}
            autoRotate={autoRotate}
            controlsRef={controlsRef}
          />
        </Suspense>
      </Canvas>

      {/* Top Left Floating Status Bar */}
      <div className="absolute top-4 left-4 z-10 flex flex-wrap items-center gap-2.5">
        <div className="px-3.5 py-1.5 rounded-full bg-white/95 backdrop-blur-md border border-[#E0DCD3] text-xs text-[#55524E] flex items-center gap-2 shadow-md">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="font-medium text-[#1A1918]">Architectural Studio 3D</span>
          <span className="text-[#CCC8BE]">|</span>
          <span>{isCutaway ? 'Dollhouse Cutaway' : 'Full Height'}</span>
        </div>

        {selectedMaterialTag && (
          <div className="px-3 py-1.5 rounded-full bg-[#C5A77B]/20 border border-[#C5A77B]/60 text-xs text-[#8A6A3E] font-medium flex items-center gap-1.5 backdrop-blur-md shadow-sm">
            <span>Highlighting: <strong className="capitalize">{selectedMaterialTag}</strong></span>
            <button
              onClick={() => setSelectedMaterialTag(null)}
              className="ml-1 text-[#8A6A3E] hover:text-[#503B1E] font-bold"
              title="Clear Highlight"
            >
              ×
            </button>
          </div>
        )}
      </div>

      {/* Selected Room Floating Inspection Card */}
      {activeRoom && (
        <div className="absolute top-16 left-4 z-10 p-3.5 rounded-xl bg-white/95 backdrop-blur-md border border-[#C5A77B]/50 shadow-xl text-xs max-w-xs animate-in fade-in slide-in-from-top-2">
          <div className="flex items-center justify-between gap-3 mb-1.5 pb-1 border-b border-[#EAE6DE]">
            <div className="flex items-center gap-1.5">
              <span className="font-bold text-sm text-[#1A1918]">{activeRoom.name}</span>
              {(activeRoom.id?.includes('flat1') || activeRoom.name?.includes('flat 1')) && (
                <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 uppercase">Flat 1</span>
              )}
              {(activeRoom.id?.includes('flat2') || activeRoom.name?.includes('flat 2')) && (
                <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-teal-100 text-teal-800 uppercase">Flat 2</span>
              )}
            </div>
            <button
              onClick={() => setActiveRoomId(null)}
              className="text-[#888] hover:text-[#111] font-bold text-sm w-5 h-5 flex items-center justify-center rounded-full hover:bg-[#F0EDE6]"
              title="Close Room Focus"
            >
              ×
            </button>
          </div>
          <div className="text-[11px] text-[#605D57] space-y-1">
            <p className="flex justify-between">
              <span>Category:</span>
              <strong className="capitalize text-[#1A1918]">{categorizeRoom(activeRoom.name, activeRoom.id)}</strong>
            </p>
            {((activeRoom as any).dimensions) && (
              <p className="flex justify-between">
                <span>Imperial Size:</span>
                <strong className="font-mono text-[#1A1918]">{(activeRoom as any).dimensions}</strong>
              </p>
            )}
            <p className="text-[10px] text-[#9E8256] pt-1">
              Camera focused on room boundaries • Click another room to inspect
            </p>
          </div>
        </div>
      )}

      {/* Top Right Floating HUD Controls Toolbar */}
      <div className="absolute top-4 right-4 z-10 flex items-center gap-1.5 bg-white/95 backdrop-blur-md p-1.5 rounded-lg border border-[#E0DCD3] shadow-md text-xs">
        {/* Toggle Cutaway View */}
        <button
          onClick={() => setIsCutaway(!isCutaway)}
          className={`px-2.5 py-1.5 rounded font-medium transition-colors ${
            isCutaway
              ? 'bg-[#1A1918] text-[#FFFFFF]'
              : 'text-[#605D57] hover:text-[#1A1918] hover:bg-[#F0EDE6]'
          }`}
          title="Toggle Cutaway / Full Height"
        >
          {isCutaway ? 'Cutaway View' : 'Full Height'}
        </button>

        {/* Toggle Clay / Realistic Mode */}
        <button
          onClick={() => setIsClay(!isClay)}
          className={`px-2.5 py-1.5 rounded font-medium transition-colors ${
            isClay
              ? 'bg-[#C5A77B] text-[#1A1918]'
              : 'text-[#605D57] hover:text-[#1A1918] hover:bg-[#F0EDE6]'
          }`}
          title="Toggle Material Realism vs Monochrome Clay"
        >
          {isClay ? 'Clay Mode' : 'Materials'}
        </button>

        {/* Toggle Furniture */}
        <button
          onClick={() => setShowFurniture(!showFurniture)}
          className={`px-2.5 py-1.5 rounded font-medium transition-colors ${
            showFurniture
              ? 'bg-[#F0EDE6] text-[#1A1918]'
              : 'text-[#999] hover:bg-[#F0EDE6]'
          }`}
          title="Toggle Furnishing"
        >
          {showFurniture ? 'Furnished' : 'Empty'}
        </button>

        {/* Toggle Labels Mode: Smart -> All -> Off */}
        <button
          onClick={() => {
            setLabelMode((prev) => (prev === 'smart' ? 'all' : prev === 'all' ? 'off' : 'smart'));
          }}
          className={`px-2.5 py-1.5 rounded font-medium transition-colors ${
            labelMode === 'smart'
              ? 'bg-[#C5A77B]/20 text-[#8A6A3E] font-semibold border border-[#C5A77B]/40'
              : labelMode === 'all'
              ? 'bg-[#1A1918] text-[#FFFFFF]'
              : 'text-[#888] hover:text-[#111] hover:bg-[#F0EDE6]'
          }`}
          title="Toggle Labels: Smart (Non-congested) / All / Off"
        >
          {labelMode === 'smart' ? 'Smart Labels' : labelMode === 'all' ? 'All Labels' : 'Labels Off'}
        </button>

        <div className="h-4 w-px bg-[#DDD9D0] mx-0.5" />

        {/* Auto-Rotate 360 */}
        <button
          onClick={() => setAutoRotate(!autoRotate)}
          className={`p-1.5 rounded hover:bg-[#F0EDE6] transition-colors ${
            autoRotate ? 'text-[#C5A77B] bg-[#C5A77B]/15' : 'text-[#605D57]'
          }`}
          title="Toggle 360° Auto-Rotate"
        >
          <IconRefresh className={`w-4 h-4 ${autoRotate ? 'animate-spin' : ''}`} />
        </button>

        {/* Reset Camera */}
        <button
          onClick={handleResetCamera}
          className="p-1.5 rounded hover:bg-[#F0EDE6] text-[#605D57] hover:text-[#1A1918] transition-colors"
          title="Reset Camera Framing"
        >
          <IconBox className="w-4 h-4" />
        </button>

        {/* Fullscreen */}
        <button
          onClick={toggleFullscreen}
          className="p-1.5 rounded hover:bg-[#F0EDE6] text-[#605D57] hover:text-[#1A1918] transition-colors"
          title="Toggle Fullscreen"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-5h-4m4 0v4m0-4l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
          </svg>
        </button>
      </div>

      {/* Bottom Room Selector Strip */}
      <div className="absolute bottom-4 left-4 right-4 z-10 flex items-center justify-between gap-3 pointer-events-none">
        <div className="flex items-center gap-1.5 overflow-x-auto p-1.5 rounded-lg bg-white/95 backdrop-blur-md border border-[#E0DCD3] shadow-md pointer-events-auto max-w-[85%] scrollbar-none">
          <button
            onClick={() => setActiveRoomId(null)}
            className={`px-3 py-1 rounded text-xs font-medium whitespace-nowrap transition-colors ${
              activeRoomId === null
                ? 'bg-[#1A1918] text-[#FFFFFF]'
                : 'text-[#605D57] hover:text-[#1A1918] hover:bg-[#F0EDE6]'
            }`}
          >
            Complete Model
          </button>
          {rooms.map((r) => (
            <button
              key={r.id}
              onClick={() => setActiveRoomId(r.id)}
              className={`px-3 py-1 rounded text-xs font-medium whitespace-nowrap transition-colors ${
                activeRoomId === r.id
                  ? 'bg-[#C5A77B] text-[#101010] font-semibold shadow-sm'
                  : 'text-[#605D57] hover:text-[#1A1918] hover:bg-[#F0EDE6]'
              }`}
            >
              {r.name || 'Room'}
            </button>
          ))}
        </div>

        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/95 backdrop-blur-md border border-[#E0DCD3] text-[11px] text-[#706C64] shadow-md pointer-events-auto">
          <span>Click room to focus • Drag to orbit • Scroll to zoom</span>
        </div>
      </div>
    </div>
  );
}
export default PlanViewer;
