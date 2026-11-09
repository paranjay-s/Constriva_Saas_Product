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
  showLabels,
  onSelect,
}: {
  room: Room;
  theme: MaterialTheme;
  isSelected: boolean;
  isHighlighted: boolean;
  isDimmed: boolean;
  showLabels: boolean;
  onSelect: () => void;
}) {
  const polygon = room.polygon || [];

  const { shape, cx, cz, width, depth, area } = useMemo(() => {
    const s = new THREE.Shape();
    if (polygon.length === 0) {
      return { shape: s, cx: 0, cz: 0, width: 0, depth: 0, area: 0 };
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

    return {
      shape: s,
      cx: minX + (maxX - minX) / 2,
      cz: minZ + (maxZ - minZ) / 2,
      width: w,
      depth: d,
      area: a,
    };
  }, [polygon]);

  const category = useMemo(() => categorizeRoom(room.name, room.id), [room.name, room.id]);
  const floorParams = useMemo(() => getRoomFloorMaterialParams(category, theme), [category, theme]);

  const color = isHighlighted
    ? '#D4B58A'
    : isSelected
    ? '#E6D2B5'
    : floorParams.color;

  const emissive = isHighlighted ? '#C5A77B' : isSelected ? '#C5A77B' : '#000000';
  const emissiveIntensity = isHighlighted ? 0.45 : isSelected ? 0.25 : 0;
  const opacity = isDimmed ? 0.5 : 1.0;

  return (
    <group>
      {/* Floor Slab Mesh (Double-Sided so it never culls) */}
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, 0.02, 0]}
        receiveShadow
        onClick={(e) => {
          e.stopPropagation();
          onSelect();
        }}
      >
        <shapeGeometry args={[shape]} />
        <meshStandardMaterial
          color={color}
          roughness={floorParams.roughness}
          metalness={floorParams.metalness}
          emissive={emissive}
          emissiveIntensity={emissiveIntensity}
          transparent={isDimmed}
          opacity={opacity}
          side={THREE.DoubleSide}
        />
      </mesh>

      {/* HTML Room Badge & Dimensions Overlay (Never suspends) */}
      {showLabels && (
        <Html
          position={[cx, 0.2, cz]}
          center
          distanceFactor={18}
          className="pointer-events-none select-none"
        >
          <div
            className={`px-2.5 py-1 rounded shadow-md border text-center transition-all ${
              isSelected
                ? 'bg-[#C5A77B] text-[#101010] border-[#9E8256] font-semibold'
                : 'bg-white/95 backdrop-blur-sm text-[#1A1918] border-[#DDD8CE]'
            }`}
          >
            <div className="text-[11px] font-bold tracking-wider uppercase font-sans whitespace-nowrap">
              {room.name || 'Room'}
            </div>
            <div className="text-[9px] text-[#706C64] font-mono whitespace-nowrap">
              {`${width}m × ${depth}m • ${area} m²`}
            </div>
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
  showLabels,
  showFurniture,
  autoRotate,
  controlsRef,
}: {
  isCutaway: boolean;
  isClay: boolean;
  showLabels: boolean;
  showFurniture: boolean;
  autoRotate: boolean;
  controlsRef: React.RefObject<any>;
}) {
  const { planData, selectedMaterialTag, activeRoomId, setActiveRoomId } = useProject();

  const theme = isClay ? CLAY_THEME : REALISTIC_THEME;
  const wallHeight = isCutaway ? 1.35 : 2.8;

  const level = planData.levels?.[0] || { walls: [], rooms: [], openings: [] };
  const walls = level.walls || [];
  const rooms = level.rooms || [];
  const openings = level.openings || [];

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
              showLabels={showLabels}
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
          .map((balconyRoom) => (
            <group key={`balcony_railings_${balconyRoom.id}`}>
              {/* Outer East edge */}
              <BalconyRailingMesh
                start={[maxX, minZ + totalD * 0.58]}
                end={[maxX, maxZ]}
                height={isCutaway ? 1.05 : 1.15}
                theme={theme}
              />
              {/* Outer North edge */}
              <BalconyRailingMesh
                start={[maxX, maxZ]}
                end={[minX + totalW * 0.58, maxZ]}
                height={isCutaway ? 1.05 : 1.15}
                theme={theme}
              />
            </group>
          ))}
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
  const [showLabels, setShowLabels] = useState(true);
  const [showFurniture, setShowFurniture] = useState(true);
  const [autoRotate, setAutoRotate] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const controlsRef = useRef<any>(null);

  const level = planData.levels?.[0] || { walls: [], rooms: [] };
  const rooms = level.rooms || [];

  // Reset Camera to complete building isometric overview
  const handleResetCamera = () => {
    setActiveRoomId(null);
    if (controlsRef.current) {
      controlsRef.current.reset();
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
        camera={{ position: [14, 18, 17], fov: 36, near: 0.1, far: 120 }}
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
            showLabels={showLabels}
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
        <div className="absolute top-16 left-4 z-10 p-3 rounded-lg bg-white/95 backdrop-blur-md border border-[#C5A77B]/40 shadow-lg text-xs max-w-xs animate-in fade-in slide-in-from-top-2">
          <div className="flex items-center justify-between gap-4 mb-1">
            <span className="font-semibold text-sm text-[#1A1918]">{activeRoom.name}</span>
            <button
              onClick={() => setActiveRoomId(null)}
              className="text-[#888] hover:text-[#111] font-bold text-sm"
              title="Close Room Focus"
            >
              ×
            </button>
          </div>
          <div className="text-[11px] text-[#706C64] space-y-0.5">
            <p>Category: <strong className="capitalize text-[#333]">{categorizeRoom(activeRoom.name, activeRoom.id)}</strong></p>
            <p>Inspection: Camera focused on room boundaries</p>
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

        {/* Toggle Labels */}
        <button
          onClick={() => setShowLabels(!showLabels)}
          className={`px-2 py-1.5 rounded transition-colors ${
            showLabels
              ? 'text-[#C5A77B] font-semibold'
              : 'text-[#888] hover:text-[#111]'
          }`}
          title="Toggle Room Labels"
        >
          Labels
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
