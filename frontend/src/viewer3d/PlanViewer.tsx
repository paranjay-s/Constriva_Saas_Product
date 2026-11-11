// PlanViewer.tsx — Thin React wrapper for vanilla Three.js Dollhouse Viewer
import { useEffect, useRef, useState, useCallback } from 'react';
import { createViewer } from './index';
import type { ViewMode, ViewerApi, WallMode } from './types';
import { normalizePlan } from './adapter/normalizePlan';

export interface PlanViewerProps {
  plan?: any;
  planJson?: any;
  highlightTag?: string | null;
  selectedRoomId?: string | null;
  onRoomSelect?: (roomId: string | null) => void;
  className?: string;
  style?: React.CSSProperties;
}

export function PlanViewer({
  plan,
  planJson,
  highlightTag = null,
  selectedRoomId = null,
  onRoomSelect,
  className = '',
  style,
}: PlanViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<ViewerApi | null>(null);

  const [viewMode, setViewMode] = useState<ViewMode>('iso');
  const [wallMode, setWallMode] = useState<WallMode>('auto');
  const [showFurniture, setShowFurniture] = useState<boolean>(true);
  const [showLabels, setShowLabels] = useState<boolean>(false);

  // Initialize vanilla Three.js viewer on container mount
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const viewer = createViewer(container, {
      initialView: viewMode,
      initialWallMode: wallMode,
      showFurniture,
      showLabels,
      onViewChange: (v) => setViewMode(v),
      onRoomSelect: (rId) => onRoomSelect?.(rId),
    });

    viewerRef.current = viewer;

    return () => {
      viewer.dispose();
      viewerRef.current = null;
    };
  }, []);

  // Update plan whenever input changes
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    const raw = plan || planJson;
    if (!raw) return;

    try {
      const normalized = normalizePlan(raw);
      viewer.loadPlan(normalized);
      if (highlightTag) {
        viewer.setMaterialHighlight(highlightTag);
      }
      if (selectedRoomId) {
        viewer.selectRoom(selectedRoomId);
      }
    } catch (err) {
      console.error('[PlanViewer] Failed to normalize and load plan:', err);
    }
  }, [plan, planJson]);

  // Sync highlight tag
  useEffect(() => {
    viewerRef.current?.setMaterialHighlight(highlightTag);
  }, [highlightTag]);

  // Sync selected room
  useEffect(() => {
    viewerRef.current?.selectRoom(selectedRoomId);
  }, [selectedRoomId]);

  const handleSetView = useCallback((v: ViewMode) => {
    setViewMode(v);
    viewerRef.current?.setView(v);
  }, []);

  const handleSetWallMode = useCallback((m: WallMode) => {
    setWallMode(m);
    viewerRef.current?.setWallMode(m);
  }, []);

  const handleToggleFurniture = useCallback(() => {
    setShowFurniture((prev) => {
      const next = !prev;
      viewerRef.current?.setFurniture(next);
      return next;
    });
  }, []);

  const handleToggleLabels = useCallback(() => {
    setShowLabels((prev) => {
      const next = !prev;
      viewerRef.current?.setLabels(next);
      return next;
    });
  }, []);

  const handleScreenshot = useCallback(() => {
    if (!viewerRef.current) return;
    const dataUrl = viewerRef.current.screenshot();
    if (!dataUrl) return;

    const link = document.createElement('a');
    link.download = `dollhouse-3d-plan-${Date.now()}.png`;
    link.href = dataUrl;
    link.click();
  }, []);

  const handleResetView = useCallback(() => {
    setViewMode('iso');
    viewerRef.current?.setView('iso');
  }, []);

  return (
    <div
      className={`relative w-full h-full overflow-hidden select-none ${className}`}
      style={style}
    >
      {/* 3D WebGL Canvas Container */}
      <div ref={containerRef} className="w-full h-full" />

      {/* Floating Dollhouse Control Toolbar (Bottom-Left) */}
      <div className="absolute bottom-4 left-4 z-20 flex flex-wrap items-center gap-1.5 p-1.5 bg-white/90 backdrop-blur-md border border-neutral-200/80 rounded-2xl shadow-lg shadow-neutral-900/5 text-xs text-neutral-700">
        {/* Camera Views: Iso vs Top */}
        <div className="flex items-center bg-neutral-100/90 rounded-xl p-0.5 border border-neutral-200/60">
          <button
            type="button"
            onClick={() => handleSetView('iso')}
            className={`px-2.5 py-1.5 font-medium rounded-lg transition-all ${
              viewMode === 'iso'
                ? 'bg-white text-neutral-900 shadow-sm font-semibold'
                : 'text-neutral-500 hover:text-neutral-800'
            }`}
            title="Isometric Dollhouse View"
          >
            Isometric
          </button>
          <button
            type="button"
            onClick={() => handleSetView('top')}
            className={`px-2.5 py-1.5 font-medium rounded-lg transition-all ${
              viewMode === 'top'
                ? 'bg-white text-neutral-900 shadow-sm font-semibold'
                : 'text-neutral-500 hover:text-neutral-800'
            }`}
            title="Top-Down Plan View"
          >
            Top
          </button>
        </div>

        <div className="w-[1px] h-5 bg-neutral-200 mx-0.5" />

        {/* Wall Modes: Auto Cutaway vs Full vs Low */}
        <div className="flex items-center bg-neutral-100/90 rounded-xl p-0.5 border border-neutral-200/60">
          <button
            type="button"
            onClick={() => handleSetWallMode('auto')}
            className={`px-2 py-1.5 rounded-lg transition-all ${
              wallMode === 'auto'
                ? 'bg-white text-neutral-900 shadow-sm font-semibold'
                : 'text-neutral-500 hover:text-neutral-800'
            }`}
            title="Dynamic Camera-Facing Cutaway"
          >
            Cutaway
          </button>
          <button
            type="button"
            onClick={() => handleSetWallMode('full')}
            className={`px-2 py-1.5 rounded-lg transition-all ${
              wallMode === 'full'
                ? 'bg-white text-neutral-900 shadow-sm font-semibold'
                : 'text-neutral-500 hover:text-neutral-800'
            }`}
            title="Full Height Walls"
          >
            Full
          </button>
          <button
            type="button"
            onClick={() => handleSetWallMode('low')}
            className={`px-2 py-1.5 rounded-lg transition-all ${
              wallMode === 'low'
                ? 'bg-white text-neutral-900 shadow-sm font-semibold'
                : 'text-neutral-500 hover:text-neutral-800'
            }`}
            title="Low Height Walls (1m)"
          >
            Low
          </button>
        </div>

        <div className="w-[1px] h-5 bg-neutral-200 mx-0.5" />

        {/* Furniture Toggle */}
        <button
          type="button"
          onClick={handleToggleFurniture}
          className={`px-2.5 py-1.5 rounded-xl border transition-all ${
            showFurniture
              ? 'bg-emerald-50 text-emerald-800 border-emerald-200/80 font-medium'
              : 'bg-white text-neutral-500 border-neutral-200 hover:bg-neutral-50'
          }`}
          title="Illustrative furniture — not part of the drawing"
        >
          Furniture {showFurniture ? 'On' : 'Off'}
        </button>

        {/* Labels Toggle */}
        <button
          type="button"
          onClick={handleToggleLabels}
          className={`px-2.5 py-1.5 rounded-xl border transition-all ${
            showLabels
              ? 'bg-blue-50 text-blue-800 border-blue-200/80 font-medium'
              : 'bg-white text-neutral-500 border-neutral-200 hover:bg-neutral-50'
          }`}
          title="Toggle Room Dimension Labels"
        >
          Labels {showLabels ? 'On' : 'Off'}
        </button>

        <div className="w-[1px] h-5 bg-neutral-200 mx-0.5" />

        {/* Screenshot Button */}
        <button
          type="button"
          onClick={handleScreenshot}
          className="px-2.5 py-1.5 bg-white text-neutral-700 hover:bg-neutral-50 border border-neutral-200 rounded-xl transition-all shadow-sm"
          title="Save High-Res Render"
        >
          Snapshot
        </button>

        {/* Reset Camera Button */}
        <button
          type="button"
          onClick={handleResetView}
          className="p-1.5 text-neutral-500 hover:text-neutral-800 hover:bg-neutral-100 rounded-xl transition-all"
          title="Reset Orbit Angle"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
        </button>
      </div>

      {/* Material Highlighting Badge Indicator */}
      {highlightTag && (
        <div className="absolute top-4 left-4 z-20 flex items-center gap-2 px-3 py-1.5 bg-amber-500/90 text-white text-xs font-semibold rounded-full shadow-md backdrop-blur-sm animate-pulse">
          <span>Highlighting: {highlightTag}</span>
        </div>
      )}
    </div>
  );
}

export default PlanViewer;
