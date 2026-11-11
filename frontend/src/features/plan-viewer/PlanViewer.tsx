// frontend/src/features/plan-viewer/PlanViewer.tsx
// Enscape-Tier 3D/4D Photorealistic Engine & Interactive FPV Walkthrough
import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { useProject } from '../../context/ProjectContext';
import type { Room } from '../../types';
import { getPbrMaterialCatalog } from './materials/materials';
import { buildWallsWithOpenings, type WallsConstructionResult } from './builders/buildWallsWithOpenings';
import { buildFloorsWithPbr, type FloorsConstructionResult } from './builders/buildFloors';
import { furnishRoomsWithPbr, type FurnishingResult } from './furniture/roomFurnisher';
import { updateProximityDoors } from './builders/buildOpenings';
import {
  CinematicNavigationRig,
  type CameraNavMode,
} from './controls/CinematicNavigationRig';
import { normalizePlan } from '../../viewer3d/adapter/normalizePlan';

export interface HighlightStyle {
  color: string;
  emissive: string;
  label: string;
  badgeBg: string;
  badgeText: string;
  badgeBorder: string;
}

export function getMaterialHighlightStyle(tagOrName: string | null): HighlightStyle {
  const t = (tagOrName || '').toLowerCase().trim();

  if (t === 'brick' || t === 'masonry' || t.includes('brick') || t.includes('masonry')) {
    return {
      color: '#E05638',
      emissive: '#C2410C',
      label: 'Brick (Masonry Walls)',
      badgeBg: 'rgba(224, 86, 56, 0.15)',
      badgeText: '#E05638',
      badgeBorder: 'rgba(224, 86, 56, 0.35)',
    };
  }
  if (t === 'steel' || t === 'rebar' || t.includes('steel') || t.includes('rebar')) {
    return {
      color: '#06B6D4',
      emissive: '#0891B2',
      label: 'Steel Reinforcement (Walls & Columns)',
      badgeBg: 'rgba(6, 182, 212, 0.15)',
      badgeText: '#06B6D4',
      badgeBorder: 'rgba(6, 182, 212, 0.35)',
    };
  }
  if (t === 'cement' || t.includes('cement') || t.includes('binder')) {
    return {
      color: '#A855F7',
      emissive: '#7E22CE',
      label: 'Cement (Concrete & Mortar)',
      badgeBg: 'rgba(168, 85, 247, 0.15)',
      badgeText: '#A855F7',
      badgeBorder: 'rgba(168, 85, 247, 0.35)',
    };
  }
  if (t === 'sand' || t.includes('sand') || t.includes('fine_aggregate')) {
    return {
      color: '#F59E0B',
      emissive: '#D97706',
      label: 'Sand (Fine Aggregate)',
      badgeBg: 'rgba(245, 158, 11, 0.15)',
      badgeText: '#F59E0B',
      badgeBorder: 'rgba(245, 158, 11, 0.35)',
    };
  }
  if (t === 'ballast' || t.includes('ballast') || t.includes('coarse_aggregate')) {
    return {
      color: '#6366F1',
      emissive: '#4338CA',
      label: 'Ballast (Coarse Aggregate)',
      badgeBg: 'rgba(99, 102, 241, 0.15)',
      badgeText: '#6366F1',
      badgeBorder: 'rgba(99, 102, 241, 0.35)',
    };
  }
  if (t === 'plaster' || t.includes('plaster')) {
    return {
      color: '#FB7185',
      emissive: '#E11D48',
      label: 'Plaster (Wall & Ceiling Finishes)',
      badgeBg: 'rgba(251, 113, 133, 0.15)',
      badgeText: '#FB7185',
      badgeBorder: 'rgba(251, 113, 133, 0.35)',
    };
  }
  if (t === 'tiles' || t.includes('tile') || t.includes('flooring') || t.includes('skirting')) {
    return {
      color: '#10B981',
      emissive: '#059669',
      label: 'Floor & Wall Tiles (Indoor Living & Wet Areas)',
      badgeBg: 'rgba(16, 185, 129, 0.15)',
      badgeText: '#10B981',
      badgeBorder: 'rgba(16, 185, 129, 0.35)',
    };
  }

  return {
    color: '#E5A93C',
    emissive: '#D97706',
    label: 'Selected Material',
    badgeBg: 'rgba(229, 169, 60, 0.15)',
    badgeText: '#E5A93C',
    badgeBorder: 'rgba(229, 169, 60, 0.35)',
  };
}

export const isIndoorTileTarget = (room: Room, cat: string): boolean => {
  const kind = (room.kind || (room as any).type || '').toLowerCase();
  if (kind === 'outdoor' || kind === 'void' || kind === 'semi_open') return false;

  const text = `${room.name || ''} ${room.id || ''}`.toLowerCase();
  if (/lawn|garden|backyard|yard|park|car|driveway|garage|porch|verandah|veranda|balcony|terrace|patio|deck|sitout|open|shaft|duct|void|stair|wash|utility|chhajja|canopy/i.test(text)) {
    return false;
  }
  if (cat === 'parking' || cat === 'lawn' || cat === 'void' || cat === 'balcony' || cat === 'utility') {
    return false;
  }
  return true;
};

export interface DetectedRoomSummary {
  id: string;
  name: string;
  dims?: string;
  areaSqFt?: number;
  areaSqM?: number;
  centroid: THREE.Vector3;
}

export function getRoomFinishDescription(
  roomName: string,
  roomType?: string
): { flooring: string; wallFinish: string } {
  const n = `${roomName} ${roomType || ''}`.toLowerCase();
  if (n.includes('bed') || n.includes('mbr')) {
    return {
      flooring: 'Warm Natural Herringbone Oak Parquet',
      wallFinish: 'Eggshell Silk Plaster with 10cm Timber Skirting',
    };
  }
  if (n.includes('liv') || n.includes('draw') || n.includes('hall') || n.includes('foyer')) {
    return {
      flooring: 'Polished Italian Carrara Marble',
      wallFinish: 'Silk Plaster with 10cm Timber Skirting & Crown Moulding',
    };
  }
  if (n.includes('bath') || n.includes('toilet') || n.includes('wc')) {
    return {
      flooring: 'Anti-Skid Matte Ceramic Tile & Marble Threshold',
      wallFinish: 'Full-Height Glazed Vitrified Dado Tiles',
    };
  }
  if (n.includes('kit') || n.includes('pantry')) {
    return {
      flooring: 'Polished Carrara Marble & Granite Borders',
      wallFinish: 'Washable Eggshell Acrylic & Quartz Splashbacks',
    };
  }
  if (
    n.includes('balcony') ||
    n.includes('terrace') ||
    n.includes('deck') ||
    n.includes('patio') ||
    n.includes('sitout') ||
    n.includes('verandah')
  ) {
    return {
      flooring: 'Weatherproof Ribbed Teak Wood Decking',
      wallFinish: 'Exterior Sand Stucco with Architectural Slate Cap',
    };
  }
  if (n.includes('park') || n.includes('garage') || n.includes('car')) {
    return {
      flooring: 'Heavy-Duty Paver Finish & Drainage Channels',
      wallFinish: 'Exterior Sand Stucco Masonry',
    };
  }
  return {
    flooring: 'Polished Italian Carrara Marble',
    wallFinish: 'Silk Plaster with 10cm Timber Skirting & Crown Moulding',
  };
}

export function getRoomIcon(roomName: string): string {
  const n = roomName.toLowerCase();
  if (n.includes('bed')) return '🛏️';
  if (n.includes('liv') || n.includes('draw')) return '🛋️';
  if (n.includes('kit')) return '🍳';
  if (n.includes('din')) return '🍽️';
  if (n.includes('bath') || n.includes('toilet') || n.includes('wc')) return '🚿';
  if (
    n.includes('balcony') ||
    n.includes('terrace') ||
    n.includes('deck') ||
    n.includes('patio') ||
    n.includes('sitout') ||
    n.includes('verandah')
  )
    return '🌿';
  if (n.includes('park') || n.includes('garage') || n.includes('car')) return '🚗';
  if (n.includes('puja') || n.includes('mandir')) return '🪔';
  return '🚪';
}

export function PlanViewer() {
  const {
    planData,
    activeRoomId,
    setActiveRoomId,
    selectedMaterialTag,
  } = useProject();

  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const modelRootRef = useRef<THREE.Group | null>(null);
  const rigRef = useRef<CinematicNavigationRig | null>(null);

  const wallsResultRef = useRef<WallsConstructionResult | null>(null);
  const floorsResultRef = useRef<FloorsConstructionResult | null>(null);
  const furnisherRef = useRef<FurnishingResult | null>(null);

  const [sceneReady, setSceneReady] = useState<boolean>(false);
  const [navMode, setNavMode] = useState<CameraNavMode>('orbit');
  const [activeRoomName, setActiveRoomName] = useState<string | null>(null);
  const [viewPreset, setViewPreset] = useState<'iso' | 'top'>('iso');
  const [timelinePhase, setTimelinePhase] = useState<number>(1.0); // 1.0 = fully built
  const [isPlayingTimeline, setIsPlayingTimeline] = useState<boolean>(false);
  const [detectedRooms, setDetectedRooms] = useState<DetectedRoomSummary[]>([]);
  const detectedRoomsRef = useRef<DetectedRoomSummary[]>([]);
  const [entranceWaypoints, setEntranceWaypoints] = useState<{ entrance: THREE.Vector3; foyer: THREE.Vector3 } | null>(null);

  // Cinematic Room Entrance Notification Banner
  const entranceTimeoutRef = useRef<number | null>(null);
  const [activeEnteringRoom, setActiveEnteringRoom] = useState<DetectedRoomSummary | null>(null);
  const [showEntranceBanner, setShowEntranceBanner] = useState<boolean>(false);
  const [currentFovPreset, setCurrentFovPreset] = useState<number>(94);

  const handleRoomEntrance = (room: {
    id: string;
    name: string;
    dims?: string;
    areaSqFt?: number;
    areaSqM?: number;
    centroid?: THREE.Vector3;
  }) => {
    setActiveRoomId(room.id);
    setActiveRoomName(room.name);

    const summary = detectedRoomsRef.current.find((r) => r.id === room.id) || {
      id: room.id,
      name: room.name,
      dims: room.dims,
      areaSqFt: room.areaSqFt,
      areaSqM: room.areaSqM,
      centroid: room.centroid || new THREE.Vector3(0, 1.5, 0),
    };

    setActiveEnteringRoom(summary);
    setShowEntranceBanner(true);

    if (entranceTimeoutRef.current) {
      window.clearTimeout(entranceTimeoutRef.current);
    }
    // Automatically transition full entrance banner to subtle top pill after 4.5 seconds
    entranceTimeoutRef.current = window.setTimeout(() => {
      setShowEntranceBanner(false);
    }, 4500);
  };

  // Setup Three.js Scene, Camera, Lights & PBR Engine
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // High performance WebGL Renderer with soft shadows
    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
      preserveDrawingBuffer: true,
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.NeutralToneMapping;
    renderer.toneMappingExposure = 1.08;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    container.innerHTML = '';
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    const scene = new THREE.Scene();
    scene.name = 'EnscapeWalkthroughScene';
    scene.background = new THREE.Color('#EBF3F9');
    sceneRef.current = scene;

    // Camera: default narrow isometric perspective (30°), auto-widens to 94° in rooms
    const camera = new THREE.PerspectiveCamera(
      30,
      container.clientWidth / container.clientHeight,
      0.04,
      350
    );
    camera.position.set(16, 18, 22);
    cameraRef.current = camera;

    // Atmospheric warm daylight & sky lighting
    const hemiLight = new THREE.HemisphereLight(0xdff0ff, 0xe8e2d5, 1.25);
    hemiLight.position.set(0, 50, 0);
    scene.add(hemiLight);

    const sunLight = new THREE.DirectionalLight(0xfff6e5, 3.2);
    sunLight.position.set(-20, 35, 18);
    sunLight.castShadow = true;
    sunLight.shadow.mapSize.width = 4096;
    sunLight.shadow.mapSize.height = 4096;
    sunLight.shadow.camera.left = -25;
    sunLight.shadow.camera.right = 25;
    sunLight.shadow.camera.top = 25;
    sunLight.shadow.camera.bottom = -25;
    sunLight.shadow.bias = -0.0003;
    sunLight.shadow.normalBias = 0.025;
    scene.add(sunLight);

    const skyFill = new THREE.DirectionalLight(0xd4e5f7, 0.9);
    skyFill.position.set(20, 16, -18);
    scene.add(skyFill);

    const modelRoot = new THREE.Group();
    modelRoot.name = 'ModelRoot';
    scene.add(modelRoot);
    modelRootRef.current = modelRoot;

    // Navigation Rig with Wide-Angle Walking & Drone Controllers
    let rafId: number;
    let lastTime = performance.now();

    const rig = new CinematicNavigationRig({
      container,
      camera,
      doors: [],
      onModeChange: (m) => setNavMode(m),
      onCeilingUpdate: (camY) => {
        floorsResultRef.current?.updateCeilingVisibility(camY);
      },
      onRoomEnter: (room) => {
        handleRoomEntrance(room);
      },
      onRequestRender: () => {},
    });
    rigRef.current = rig;

    // Render & Animation Loop
    const animate = () => {
      rafId = requestAnimationFrame(animate);
      const now = performance.now();
      const delta = (now - lastTime) / 1000;
      lastTime = now;

      rig.update(delta);

      if (wallsResultRef.current) {
        updateProximityDoors(wallsResultRef.current.doors, camera.position, delta);
      }

      renderer.render(scene, camera);
    };
    rafId = requestAnimationFrame(animate);

    // Resize observer
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          camera.aspect = width / height;
          camera.updateProjectionMatrix();
          renderer.setSize(width, height);
        }
      }
    });
    resizeObserver.observe(container);

    // Raycast room floor clicks to teleport into room at human eye level (1.50m) with panoramic FOV
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    const onPointerDown = (event: MouseEvent) => {
      if (rig.mode !== 'orbit') return;

      const rect = container.getBoundingClientRect();
      mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

      raycaster.setFromCamera(mouse, camera);
      const floorMeshes = Array.from(floorsResultRef.current?.roomMeshes.values() || []);
      const intersects = raycaster.intersectObjects(floorMeshes);

      if (intersects.length > 0) {
        const hit = intersects[0];
        const point = hit.point;
        const rName = hit.object.userData?.roomName || 'Room';
        const rId = hit.object.userData?.roomId;
        if (rId) setActiveRoomId(rId);
        setActiveRoomName(rName);

        const targetSummary = detectedRoomsRef.current.find((r) => r.id === rId);
        if (targetSummary) {
          handleRoomEntrance(targetSummary);
        }
        rig.teleportToRoom(
          new THREE.Vector3(point.x, 1.50, point.z),
          undefined,
          targetSummary
            ? {
                id: targetSummary.id,
                name: targetSummary.name,
                polygon: [],
                dims: targetSummary.dims,
                areaSqFt: targetSummary.areaSqFt,
                areaSqM: targetSummary.areaSqM,
              }
            : undefined
        );
      }
    };
    container.addEventListener('dblclick', onPointerDown);

    setSceneReady(true);

    return () => {
      cancelAnimationFrame(rafId);
      resizeObserver.disconnect();
      container.removeEventListener('dblclick', onPointerDown);
      if (entranceTimeoutRef.current) {
        window.clearTimeout(entranceTimeoutRef.current);
      }
      rig.dispose();
      renderer.dispose();
      setSceneReady(false);
    };
  }, []);

  // Rebuild 3D Model when planData updates
  useEffect(() => {
    if (!sceneReady) return;
    const modelRoot = modelRootRef.current;
    const rig = rigRef.current;
    const camera = cameraRef.current;
    if (!modelRoot || !rig || !camera) return;

    if (!planData) return;

    // Use normalizePlan to robustly parse both array [x,y] and object {x,y} coordinates,
    // synthesize missing partition walls between adjacent rooms, and center origin
    const plan = normalizePlan(planData);
    if (plan.walls.length === 0 && plan.rooms.length === 0) return;

    const mats = getPbrMaterialCatalog();

    // Cleanly clear prior model children
    while (modelRoot.children.length > 0) {
      modelRoot.remove(modelRoot.children[0]);
    }

    // Format rooms data for builders
    const roomsData = plan.rooms.map((r) => ({
      id: r.id,
      name: r.label || r.id,
      type: r.type,
      polygon: r.polygon,
    }));

    // 1. Build Plinth, Multi-zone PBR Floors & Auto-culling Smart Ceilings
    const floorsRes = buildFloorsWithPbr(roomsData, mats, (rId) => {
      setActiveRoomId(rId);
    });
    floorsResultRef.current = floorsRes;
    modelRoot.add(floorsRes.group);

    // 2. Build Sliced Walls with Lintels, Window Sills, Skirting & Openings
    const wallsRes = buildWallsWithOpenings(plan.walls, plan.openings, mats);
    wallsResultRef.current = wallsRes;
    modelRoot.add(wallsRes.group);
    rig.doors = wallsRes.doors;

    // 3. Auto-Stage PBR Furniture, Outdoor Lounge Deck Suites & Plants
    const furnRes = furnishRoomsWithPbr(roomsData, mats);
    furnisherRef.current = furnRes;
    modelRoot.add(furnRes.group);

    // 4. Compute Room Summaries & Exact Dimensions for Click-to-Enter Teleportation & Labels
    let foyerPt = new THREE.Vector3(0, 1.50, 0);
    let entrancePt = new THREE.Vector3(0, 1.55, 6);

    const roomSummaries: DetectedRoomSummary[] = [];
    for (const r of plan.rooms) {
      if (r.polygon.length < 3) continue;
      const sx = r.polygon.reduce((acc, p) => acc + p.x, 0) / r.polygon.length;
      const sz = r.polygon.reduce((acc, p) => acc + p.y, 0) / r.polygon.length;
      const centroid = new THREE.Vector3(sx, 1.50, sz);

      // Compute room area via Shoelace formula
      let areaM2 = 0;
      for (let i = 0; i < r.polygon.length; i++) {
        const j = (i + 1) % r.polygon.length;
        areaM2 += r.polygon[i].x * r.polygon[j].y;
        areaM2 -= r.polygon[j].x * r.polygon[i].y;
      }
      areaM2 = Math.abs(areaM2) / 2;
      const areaSqFt = Math.round(areaM2 * 10.7639);

      const dimsText =
        r.dims && (r.dims.w > 0 || r.dims.d > 0)
          ? `${Math.round(r.dims.w * 3.28084)}' × ${Math.round(r.dims.d * 3.28084)}' • ${areaSqFt} sq ft`
          : `${areaSqFt} sq ft (${areaM2.toFixed(1)} m²)`;

      const summary: DetectedRoomSummary = {
        id: r.id,
        name: r.label || r.id,
        dims: dimsText,
        areaSqFt,
        areaSqM: areaM2,
        centroid,
      };
      roomSummaries.push(summary);

      const n = (r.label || r.id).toLowerCase();
      if (n.includes('living') || n.includes('entry') || n.includes('foyer') || n.includes('drawing')) {
        foyerPt = centroid.clone();
        entrancePt = new THREE.Vector3(centroid.x, 1.55, centroid.z + 5.5);
      }
    }

    setDetectedRooms(roomSummaries);
    detectedRoomsRef.current = roomSummaries;
    setEntranceWaypoints({ entrance: entrancePt, foyer: foyerPt });

    // Populate rig.rooms with polygon geometry for live room-entry tracking
    rig.rooms = plan.rooms.map((r, i) => {
      const summary = roomSummaries[i];
      return {
        id: r.id,
        name: r.label || r.id,
        polygon: r.polygon,
        dims: summary?.dims,
        areaSqFt: summary?.areaSqFt,
        areaSqM: summary?.areaSqM,
      };
    });

    // 5. Fit & Frame Camera to Entire House (Isometric Perspective)
    const box = new THREE.Box3().setFromObject(modelRoot);
    const sphere = box.getBoundingSphere(new THREE.Sphere());
    const radius = Math.max(sphere.radius, 6);
    const center = sphere.center;

    if (rig.mode === 'orbit') {
      rig.controls.target.copy(center);
      const isoDist = radius * 2.3;
      camera.position.set(
        center.x + isoDist * 0.72,
        center.y + isoDist * 0.85,
        center.z + isoDist * 0.95
      );
      camera.lookAt(center);
      rig.controls.update();
    }
  }, [sceneReady, planData]);

  // Synchronize Material Highlighting from BOQ Sheet
  useEffect(() => {
    wallsResultRef.current?.updateHighlight(selectedMaterialTag);
    floorsResultRef.current?.updateHighlight(selectedMaterialTag);
  }, [selectedMaterialTag]);

  // Synchronize Active Room
  useEffect(() => {
    floorsResultRef.current?.selectRoom(activeRoomId);
  }, [activeRoomId]);

  // 4D Construction Buildup Scrubber Controller
  const handleTimelineChange = (phase: number) => {
    setTimelinePhase(phase);
    floorsResultRef.current?.setConstructionPhase(phase);
    wallsResultRef.current?.setConstructionPhase(phase);
    furnisherRef.current?.setConstructionPhase(phase);
  };

  // Play / Pause 4D Construction Animation
  useEffect(() => {
    if (!isPlayingTimeline) return;
    const interval = setInterval(() => {
      setTimelinePhase((prev) => {
        const next = prev + 0.02;
        if (next >= 1.0) {
          setIsPlayingTimeline(false);
          handleTimelineChange(1.0);
          return 1.0;
        }
        handleTimelineChange(next);
        return next;
      });
    }, 45);
    return () => clearInterval(interval);
  }, [isPlayingTimeline]);

  // Camera preset views
  const handleSetIsoView = () => {
    setViewPreset('iso');
    const rig = rigRef.current;
    const modelRoot = modelRootRef.current;
    if (!rig || !modelRoot) return;
    const box = new THREE.Box3().setFromObject(modelRoot);
    const sphere = box.getBoundingSphere(new THREE.Sphere());
    const radius = Math.max(sphere.radius, 6);
    const center = sphere.center;
    const isoDist = radius * 2.3;
    rig.setMode('orbit');
    setActiveRoomName(null);
    rig.animateTo(
      new THREE.Vector3(
        center.x + isoDist * 0.72,
        center.y + isoDist * 0.85,
        center.z + isoDist * 0.95
      ),
      center,
      1.2
    );
  };

  const handleSetTopView = () => {
    setViewPreset('top');
    const rig = rigRef.current;
    const modelRoot = modelRootRef.current;
    if (!rig || !modelRoot) return;
    const box = new THREE.Box3().setFromObject(modelRoot);
    const sphere = box.getBoundingSphere(new THREE.Sphere());
    const radius = Math.max(sphere.radius, 6);
    const center = sphere.center;
    rig.setMode('orbit');
    setActiveRoomName(null);
    rig.animateTo(
      new THREE.Vector3(center.x, radius * 2.8, center.z + 0.001),
      center,
      1.2
    );
  };

  const handlePlayWelcomeTour = () => {
    if (!entranceWaypoints || !rigRef.current) return;
    setActiveRoomName('Front Entrance Arrival');
    rigRef.current.playWelcomeArrival(entranceWaypoints.entrance, entranceWaypoints.foyer);
  };

  const handleStartDroneTour = () => {
    if (detectedRooms.length < 2 || !rigRef.current) return;
    const waypoints = detectedRooms.map((r) => r.centroid.clone().setY(1.50));
    setActiveRoomName('Autonomous FPV Drone Tour');
    rigRef.current.startDroneTour(waypoints);
  };

  const handleStopDroneTour = () => {
    rigRef.current?.stopTour();
    setNavMode('orbit');
    setActiveEnteringRoom(null);
    setShowEntranceBanner(false);
    handleSetIsoView();
  };

  // Teleport into Room with ultra-wide panoramic lens (94° FOV) and entrance notification
  const handleTeleportRoom = (room: DetectedRoomSummary) => {
    handleRoomEntrance(room);
    rigRef.current?.teleportToRoom(room.centroid, undefined, {
      id: room.id,
      name: room.name,
      polygon: [],
      dims: room.dims,
      areaSqFt: room.areaSqFt,
      areaSqM: room.areaSqM,
    });
  };

  // Return to Orbit
  const handleExitToOrbit = () => {
    setActiveEnteringRoom(null);
    setShowEntranceBanner(false);
    handleSetIsoView();
  };

  return (
    <div className="relative w-full h-full min-h-[580px] bg-[#EBF3F9] overflow-hidden select-none font-sans">
      {/* 3D WebGL Canvas */}
      <div ref={containerRef} className="w-full h-full cursor-grab active:cursor-grabbing" />

      {/* Cinematic Room Entrance Title Card / Banner (Appears only when entering any room) */}
      {activeEnteringRoom && showEntranceBanner && (
        <div className="absolute top-16 left-1/2 -translate-x-1/2 z-30 max-w-lg w-[92%] sm:w-auto pointer-events-auto">
          <div className="relative px-5 py-3.5 rounded-2xl bg-slate-950/90 backdrop-blur-xl border border-emerald-500/40 shadow-2xl shadow-emerald-950/40 text-white flex flex-col gap-1.5 ring-1 ring-white/10">
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
                <span className="text-[10px] font-bold tracking-widest text-emerald-400 uppercase">
                  Entering Room
                </span>
              </div>
              <button
                type="button"
                onClick={() => setShowEntranceBanner(false)}
                className="text-white/40 hover:text-white text-xs px-1.5 py-0.5 rounded hover:bg-white/10"
                title="Dismiss"
              >
                ✕
              </button>
            </div>

            <div className="flex items-baseline gap-2">
              <span className="text-xl">{getRoomIcon(activeEnteringRoom.name)}</span>
              <h2 className="text-base sm:text-lg font-bold tracking-tight text-white uppercase">
                {activeEnteringRoom.name}
              </h2>
              {activeEnteringRoom.dims && (
                <span className="text-xs font-medium text-emerald-300 font-mono">
                  {activeEnteringRoom.dims}
                </span>
              )}
            </div>

            <div className="text-[11px] text-slate-300 flex flex-col gap-0.5 pt-1 border-t border-white/10">
              <div>
                <span className="text-slate-400">Flooring:</span>{' '}
                <span className="text-slate-200 font-medium">
                  {getRoomFinishDescription(activeEnteringRoom.name).flooring}
                </span>
              </div>
              <div>
                <span className="text-slate-400">Walls:</span>{' '}
                <span className="text-slate-200 font-medium">
                  {getRoomFinishDescription(activeEnteringRoom.name).wallFinish}
                </span>
              </div>
            </div>

            <div className="flex items-center justify-between text-[10px] text-white/50 pt-1 border-t border-white/5">
              <span>WASD or Scroll Wheel to Walk • Drag to Look 360°</span>
              <span className="text-emerald-400 font-medium">Panoramic Lens ({currentFovPreset}°)</span>
            </div>
          </div>
        </div>
      )}

      {/* Top Left: Mode & Status Indicator */}
      <div className="absolute top-4 left-4 z-20 flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-slate-900/85 backdrop-blur-md border border-white/10 text-xs text-white shadow-lg">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="font-semibold tracking-wide">Enscape 4D Studio</span>
          <span className="text-white/30">|</span>
          <span className="text-white/80 capitalize">
            {navMode === 'walkthrough'
              ? `Inside: ${activeRoomName || 'Room'} (${currentFovPreset}° Panoramic)`
              : navMode === 'drone'
              ? 'Autonomous Drone Tour'
              : 'Isometric Aerial View'}
          </span>
        </div>

        {selectedMaterialTag && (
          <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-amber-500/90 text-white text-xs font-semibold shadow-md backdrop-blur-md animate-pulse">
            <span>BOQ Highlight: {selectedMaterialTag}</span>
          </div>
        )}
      </div>

      {/* Top Right: View Controls, Drone Tour Stop & Panoramic Lens Switchers */}
      <div className="absolute top-4 right-4 z-20 flex items-center gap-2">
        {navMode === 'drone' ? (
          <button
            type="button"
            onClick={handleStopDroneTour}
            className="flex items-center gap-2 px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs rounded-full shadow-xl shadow-rose-600/40 animate-pulse transition-all border border-rose-300 ring-2 ring-rose-500/50"
            title="Stop the automated drone tour and return to orbit (or press ESC / Space)"
          >
            <span className="w-2.5 h-2.5 rounded-sm bg-white" />
            <span>STOP DRONE TOUR</span>
            <span className="text-[10px] bg-rose-950/70 px-1.5 py-0.5 rounded text-white font-mono font-bold">ESC</span>
          </button>
        ) : navMode === 'walkthrough' ? (
          <div className="flex items-center gap-1.5 p-1 bg-slate-900/85 backdrop-blur-md border border-white/10 rounded-full shadow-lg text-xs">
            <span className="text-[11px] font-semibold text-white/50 px-2 uppercase tracking-wider">Lens:</span>
            <button
              type="button"
              onClick={() => {
                setCurrentFovPreset(84);
                rigRef.current?.setCustomFov(84);
              }}
              className={`px-2.5 py-1 rounded-full font-medium transition-all ${
                currentFovPreset === 84
                  ? 'bg-emerald-500 text-slate-950 font-bold'
                  : 'text-white/80 hover:text-white hover:bg-white/10'
              }`}
              title="84° Wide Lens"
            >
              84° Wide
            </button>
            <button
              type="button"
              onClick={() => {
                setCurrentFovPreset(94);
                rigRef.current?.setCustomFov(94);
              }}
              className={`px-2.5 py-1 rounded-full font-medium transition-all ${
                currentFovPreset === 94
                  ? 'bg-emerald-500 text-slate-950 font-bold'
                  : 'text-white/80 hover:text-white hover:bg-white/10'
              }`}
              title="94° Panoramic Lens (Optimal View)"
            >
              94° Panoramic
            </button>
            <button
              type="button"
              onClick={() => {
                setCurrentFovPreset(104);
                rigRef.current?.setCustomFov(104);
              }}
              className={`px-2.5 py-1 rounded-full font-medium transition-all ${
                currentFovPreset === 104
                  ? 'bg-emerald-500 text-slate-950 font-bold'
                  : 'text-white/80 hover:text-white hover:bg-white/10'
              }`}
              title="104° Ultra-Wide Lens (Full Ceiling & Floor View)"
            >
              104° Ultra
            </button>
            <div className="w-[1px] h-3.5 bg-white/20 mx-0.5" />
            <button
              type="button"
              onClick={() => {
                const next = Math.max(60, currentFovPreset - 5);
                setCurrentFovPreset(next);
                rigRef.current?.setCustomFov(next);
              }}
              className="w-6 h-6 flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 text-white font-bold"
              title="Zoom In (Decrease FOV)"
            >
              +
            </button>
            <button
              type="button"
              onClick={() => {
                const next = Math.min(115, currentFovPreset + 5);
                setCurrentFovPreset(next);
                rigRef.current?.setCustomFov(next);
              }}
              className="w-6 h-6 flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 text-white font-bold"
              title="Zoom Out (Expand FOV)"
            >
              -
            </button>
            <div className="w-[1px] h-3.5 bg-white/20 mx-0.5" />
            <button
              type="button"
              onClick={handleExitToOrbit}
              className="px-3 py-1 bg-white/15 hover:bg-white/25 text-white font-semibold rounded-full transition-all"
              title="Exit walkthrough to aerial orbit"
            >
              Exit to Aerial Orbit
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 p-1 bg-slate-900/85 backdrop-blur-md border border-white/10 rounded-full shadow-lg text-xs">
            <button
              type="button"
              onClick={handleSetIsoView}
              className={`px-3 py-1 rounded-full font-medium transition-all ${
                viewPreset === 'iso'
                  ? 'bg-emerald-500 text-slate-950 font-bold shadow-sm'
                  : 'text-white/80 hover:text-white'
              }`}
            >
              Isometric
            </button>
            <button
              type="button"
              onClick={handleSetTopView}
              className={`px-3 py-1 rounded-full font-medium transition-all ${
                viewPreset === 'top'
                  ? 'bg-emerald-500 text-slate-950 font-bold shadow-sm'
                  : 'text-white/80 hover:text-white'
              }`}
            >
              Top Plan
            </button>
            <div className="w-[1px] h-3.5 bg-white/20 mx-0.5" />
            <button
              type="button"
              onClick={handlePlayWelcomeTour}
              className="px-2.5 py-1 text-white/90 hover:text-white hover:bg-white/10 rounded-full font-medium transition-all"
              title="Play realistic welcome walk entering front door"
            >
              Welcome Walk
            </button>
            <button
              type="button"
              onClick={handleStartDroneTour}
              className="px-3 py-1 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-semibold rounded-full shadow-sm transition-all"
              title="Autonomous Higgsfield Drone Tour"
            >
              Drone Tour
            </button>
          </div>
        )}
      </div>

      {/* Center Prompt when in Drone Tour mode */}
      {navMode === 'drone' && (
        <div className="absolute top-16 left-1/2 -translate-x-1/2 z-30 flex items-center gap-3 px-5 py-2 bg-black/85 backdrop-blur-md text-white/95 text-xs rounded-full border border-rose-500/50 shadow-2xl pointer-events-auto">
          <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-ping" />
          <span>Autonomous Drone Tour in Progress</span>
          <button
            type="button"
            onClick={handleStopDroneTour}
            className="px-2.5 py-0.5 bg-rose-600 hover:bg-rose-500 text-white font-bold text-[11px] rounded-full shadow border border-rose-400"
          >
            ⏹ Stop (ESC)
          </button>
        </div>
      )}

      {/* Center Prompt when in Walkthrough mode */}
      {navMode === 'walkthrough' && !showEntranceBanner && (
        <div className="absolute top-16 left-1/2 -translate-x-1/2 z-10 px-4 py-1.5 bg-black/70 backdrop-blur-md text-white/95 text-xs rounded-full border border-white/15 pointer-events-none shadow-md flex items-center gap-2">
          <span>Panoramic {currentFovPreset}° Lens</span>
          <span className="text-white/30">•</span>
          <span>Drag to Look 360° (Look Up/Down)</span>
          <span className="text-white/30">•</span>
          <span>WASD or Scroll Wheel to Walk</span>
          <span className="text-white/30">•</span>
          <span className="text-emerald-400 font-medium">Double-click floor to step</span>
        </div>
      )}

      {/* Bottom Area: 4D Construction Scrubber & Room Navigation Chips */}
      <div className="absolute bottom-4 left-4 right-4 z-20 flex flex-col gap-2 max-w-4xl mx-auto">
        {/* 4D Construction Buildup Slider */}
        <div className="flex items-center gap-3 px-4 py-2 bg-slate-900/85 backdrop-blur-md border border-white/10 rounded-2xl shadow-xl text-white text-xs">
          <button
            type="button"
            onClick={() => {
              if (timelinePhase >= 1.0) handleTimelineChange(0);
              setIsPlayingTimeline(!isPlayingTimeline);
            }}
            className="px-2.5 py-1 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold rounded-lg transition-all"
          >
            {isPlayingTimeline ? 'Pause' : 'Play 4D Build'}
          </button>

          <span className="text-white/60 font-medium whitespace-nowrap min-w-[150px]">
            {timelinePhase < 0.25
              ? 'Phase 1: Plinth & Site'
              : timelinePhase < 0.6
              ? 'Phase 2: Walls & Lintels'
              : timelinePhase < 0.8
              ? 'Phase 3: Doors & Windows'
              : 'Phase 4: Staged Realism'}
          </span>

          <input
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={timelinePhase}
            onChange={(e) => handleTimelineChange(parseFloat(e.target.value))}
            className="w-full accent-emerald-400 h-1.5 bg-white/20 rounded-lg cursor-pointer"
          />

          <span className="font-mono text-emerald-400 w-10 text-right">
            {Math.round(timelinePhase * 100)}%
          </span>
        </div>

        {/* Room Navigation Selector (Click to Enter Room) */}
        {detectedRooms.length > 0 && (
          <div className="flex items-center gap-1.5 overflow-x-auto p-1.5 bg-slate-900/85 backdrop-blur-md border border-white/10 rounded-2xl shadow-xl scrollbar-none">
            <span className="text-[11px] font-semibold text-white/50 px-2 uppercase tracking-wider whitespace-nowrap">
              Explore:
            </span>
            <button
              type="button"
              onClick={handleExitToOrbit}
              className={`px-3 py-1 text-xs rounded-xl font-medium whitespace-nowrap transition-all flex items-center gap-1.5 ${
                navMode === 'orbit'
                  ? 'bg-emerald-500 text-slate-950 shadow-md font-bold'
                  : 'bg-white/10 text-white/90 hover:bg-white/20'
              }`}
              title="View entire house from aerial dollhouse cutaway"
            >
              <span>🏠</span>
              <span>Complete House</span>
            </button>
            {detectedRooms.map((room) => {
              const isActive = navMode === 'walkthrough' && activeRoomName === room.name;
              return (
                <button
                  key={room.id}
                  type="button"
                  onClick={() => handleTeleportRoom(room)}
                  className={`px-3 py-1 text-xs rounded-xl font-medium whitespace-nowrap transition-all flex items-center gap-1.5 ${
                    isActive
                      ? 'bg-emerald-500 text-slate-950 shadow-md font-bold ring-2 ring-emerald-300'
                      : 'bg-white/10 text-white/90 hover:bg-white/20'
                  }`}
                  title={`Enter and inspect ${room.name} in first-person (360° panoramic)`}
                >
                  <span>{getRoomIcon(room.name)}</span>
                  <span>{room.name}</span>
                  {room.areaSqFt && room.areaSqFt > 0 && (
                    <span className="opacity-60 text-[10px]">({room.areaSqFt} sq ft)</span>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default PlanViewer;
