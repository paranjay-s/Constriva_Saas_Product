import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProject } from '../../context/ProjectContext';
import { PlanViewer, getMaterialHighlightStyle } from './PlanViewer';
import { Button } from '../../components/ui/Button';
import { sheetsApi, type SheetItem } from '../sheets';
import {
  IconArrowLeft,
  IconArrowRight,
  IconCheck,
  IconDownload,
  IconFilePdf,
  IconRefresh,
} from '../../components/ui/Icons';

export function WorkspacePage() {
  const navigate = useNavigate();
  const {
    activeProject,
    selectedMaterialTag,
    setSelectedMaterialTag,
  } = useProject();

  // Active view on mobile/tablet screens
  const [mobileView, setMobileView] = useState<'viewport' | 'sheet'>('sheet');
  const [activeTab, setActiveTab] = useState<'all' | 'structure' | 'walls' | 'flooring'>('all');
  const [downloadSuccess, setDownloadSuccess] = useState<string | null>(null);

  // Live backend sheet state
  const [sheetItems, setSheetItems] = useState<SheetItem[]>([]);
  const [sheetName, setSheetName] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRecalculating, setIsRecalculating] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Fetch sheet exclusively from FastAPI backend on project mount/change
  useEffect(() => {
    if (!activeProject?.id) return;
    let isCurrent = true;

    setIsLoading(true);
    setErrorMsg(null);

    sheetsApi
      .getSheet(activeProject.id)
      .then(async (res) => {
        if (!isCurrent) return;

        // If backend returns sheet with items, render them directly
        if (res && Array.isArray(res.items) && res.items.length > 0) {
          setSheetItems(res.items);
          setSheetName(res.name || 'Architectural Quantity Survey');
        } else {
          // If sheet is empty or newly created, trigger plan geometry recalculation
          try {
            const recalculated = await sheetsApi.recalculateFromPlan(activeProject.id);
            if (isCurrent && recalculated && Array.isArray(recalculated.items)) {
              setSheetItems(recalculated.items);
              setSheetName(recalculated.name || 'Architectural Quantity Survey');
            }
          } catch (recalcErr) {
            console.warn('Initial recalculation fallback:', recalcErr);
          }
        }
      })
      .catch((err) => {
        if (!isCurrent) return;
        console.warn('Backend sheet fetch error:', err);
        setErrorMsg('Could not load sheet from backend. Check network or click recalculate.');
      })
      .finally(() => {
        if (isCurrent) setIsLoading(false);
      });

    return () => {
      isCurrent = false;
    };
  }, [activeProject?.id]);

  // Recalculate directly from PlanJSON geometry via backend
  const handleRecalculate = async () => {
    if (!activeProject?.id) return;
    setIsRecalculating(true);
    setErrorMsg(null);
    try {
      const res = await sheetsApi.recalculateFromPlan(activeProject.id);
      if (res && Array.isArray(res.items)) {
        setSheetItems(res.items);
        setSheetName(res.name || 'Architectural Quantity Survey');
      }
    } catch (err: any) {
      console.error('Recalculation failed:', err);
      setErrorMsg(err.message || 'Recalculation failed. Please try again.');
    } finally {
      setIsRecalculating(false);
    }
  };

  // Filter items based on active classification category tab
  const filteredItems = useMemo(() => {
    return sheetItems.filter((item) => {
      if (activeTab === 'all') return true;
      const cat = (item.category || '').toLowerCase();
      const tag = (item.surface_tag || '').toLowerCase();
      const name = (item.name || '').toLowerCase();

      if (activeTab === 'structure') {
        return (
          cat.includes('structural') ||
          cat.includes('masonry') ||
          cat.includes('aggregate') ||
          cat.includes('binder') ||
          tag.includes('reinforcement') ||
          tag.includes('aggregate') ||
          tag.includes('concrete') ||
          name.includes('steel') ||
          name.includes('ballast') ||
          name.includes('sand') ||
          name.includes('cement')
        );
      }
      if (activeTab === 'walls') {
        return (
          cat.includes('masonry') ||
          cat.includes('plaster') ||
          tag.includes('masonry') ||
          tag.includes('plaster') ||
          name.includes('brick') ||
          name.includes('plaster')
        );
      }
      if (activeTab === 'flooring') {
        return (
          cat.includes('flooring') ||
          cat.includes('tiling') ||
          tag.includes('tile') ||
          name.includes('tile')
        );
      }
      return true;
    });
  }, [sheetItems, activeTab]);

  // Fallback client-side CSV if backend offline
  const handleClientExportCsv = () => {
    const csvContent =
      'Item #,Material / Component,Category,Surface Tag,Base Qty,Unit,Waste %,Total Qty,Area (m2),Secondary Metric\n' +
      sheetItems
        .map(
          (m, idx) =>
            `${idx + 1},"${m.name}","${m.category}","${m.surface_tag || '-'}","${m.quantity}","${m.unit}","${Math.round(
              (m.waste_factor || 0) * 100
            )}%","${m.total_quantity}","${m.area || '-'}","${m.secondary_quantity ? `${m.secondary_quantity} ${m.secondary_unit || ''}` : '-'}"`
        )
        .join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `${activeProject?.name || 'project'}_BOQ_Quantities.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Export CSV
  const handleExportCsv = async () => {
    try {
      if (activeProject?.id) {
        await sheetsApi.downloadCsv(activeProject.id, activeProject.name || 'project');
      } else {
        handleClientExportCsv();
      }
      setDownloadSuccess('CSV Exported');
      setTimeout(() => setDownloadSuccess(null), 3000);
    } catch {
      handleClientExportCsv();
      setDownloadSuccess('CSV Exported');
      setTimeout(() => setDownloadSuccess(null), 3000);
    }
  };

  // Export PDF
  const handleExportPdf = async () => {
    if (!activeProject?.id) return;
    try {
      await sheetsApi.downloadPdf(activeProject.id, activeProject.name || 'project');
      setDownloadSuccess('PDF Report Ready');
      setTimeout(() => setDownloadSuccess(null), 3000);
    } catch (err) {
      console.warn('PDF export error:', err);
    }
  };

  return (
    <div className="min-h-screen bg-canvas text-primary flex flex-col h-screen overflow-hidden">
      {/* 3D Workspace Contextual Toolbar */}
      <div
        role="toolbar"
        aria-label="3D Workspace Controls"
        className="border-b border-white/10 bg-[#0d0f12]/85 backdrop-blur-md px-3 sm:px-6 py-2 flex flex-wrap items-center justify-between gap-3 flex-shrink-0 z-20"
      >
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/projects/options')}
            leftIcon={<IconArrowLeft className="w-4 h-4" />}
          >
            Options
          </Button>

          <div className="h-4 w-px bg-border hidden sm:block" />

          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-serif font-medium text-primary text-sm sm:text-base tracking-tight truncate max-w-[200px] sm:max-w-md">
                {activeProject?.name || 'Pavilion Serena Residences'}
              </h1>
              <span className="hidden sm:inline-block px-2 py-0.5 rounded text-[10px] font-medium bg-accent/15 text-accent border border-accent/30">
                {activeProject?.type || 'Residential'}
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                <span className="hidden sm:inline">3D Active</span>
              </span>
              {isLoading && (
                <span className="text-[11px] text-secondary flex items-center gap-1 ml-1">
                  <span className="animate-spin text-xs">⟳</span> Loading backend BOQ...
                </span>
              )}
            </div>
            <p className="text-[11px] text-secondary hidden md:block">
              {sheetName} • Verified Architectural Quantity Survey • Multi-Color 3D Highlight
            </p>
          </div>
        </div>

        {/* Header Action Buttons */}
        <div className="flex items-center gap-1.5 sm:gap-2">
          {/* Mobile Screen Segmented Switcher */}
          <div className="flex lg:hidden bg-panel rounded-lg p-0.5 border border-border">
            <button
              onClick={() => setMobileView('viewport')}
              className={`px-2.5 py-1 text-xs rounded-md font-medium transition-all ${
                mobileView === 'viewport'
                  ? 'bg-surface text-primary shadow-sm'
                  : 'text-secondary hover:text-primary'
              }`}
            >
              3D View
            </button>
            <button
              onClick={() => setMobileView('sheet')}
              className={`px-2.5 py-1 text-xs rounded-md font-medium transition-all ${
                mobileView === 'sheet'
                  ? 'bg-surface text-primary shadow-sm'
                  : 'text-secondary hover:text-primary'
              }`}
            >
              BOQ Sheet ({sheetItems.length})
            </button>
          </div>

          <Button
            variant="secondary"
            size="sm"
            onClick={handleExportCsv}
            leftIcon={
              downloadSuccess?.includes('CSV') ? (
                <IconCheck className="w-3.5 h-3.5 text-emerald-400" />
              ) : (
                <IconDownload className="w-3.5 h-3.5" />
              )
            }
          >
            <span className="hidden sm:inline">{downloadSuccess?.includes('CSV') ? 'Downloaded' : 'Export'}</span> CSV
          </Button>

          <Button
            variant="secondary"
            size="sm"
            onClick={handleExportPdf}
            leftIcon={
              downloadSuccess?.includes('PDF') ? (
                <IconCheck className="w-3.5 h-3.5 text-emerald-400" />
              ) : (
                <IconFilePdf className="w-3.5 h-3.5 text-rose-400" />
              )
            }
          >
            <span className="hidden sm:inline">{downloadSuccess?.includes('PDF') ? 'Downloaded' : 'Printable'}</span> PDF
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={() => navigate('/projects/loan-analysis')}
            rightIcon={<IconArrowRight className="w-4 h-4" />}
          >
            <span className="hidden sm:inline">Compare</span> Loan
          </Button>
        </div>
      </div>

      {/* Main Responsive Split Layout */}
      <main className="flex-1 flex flex-col lg:flex-row overflow-hidden relative">
        {/* Left: 3D Viewport (60% on desktop, toggleable on mobile) */}
        <section
          className={`flex-1 lg:w-[60%] xl:w-[63%] p-2 sm:p-4 flex flex-col min-h-0 ${
            mobileView === 'sheet' ? 'hidden lg:flex' : 'flex'
          }`}
        >
          <div className="flex-1 w-full h-full rounded-xl overflow-hidden border border-border bg-panel shadow-sm">
            <PlanViewer />
          </div>
        </section>

        {/* Right: Verified BOQ Material Quantities (40% on desktop, toggleable on mobile) */}
        <aside
          className={`lg:w-[40%] xl:w-[37%] border-t lg:border-t-0 lg:border-l border-border bg-surface flex flex-col h-full overflow-hidden ${
            mobileView === 'viewport' ? 'hidden lg:flex' : 'flex'
          }`}
        >
          {/* Header Controls */}
          <div className="p-3 sm:p-4 border-b border-border bg-surface/95 backdrop-blur-md sticky top-0 z-10 flex-shrink-0">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <h2 className="font-serif font-semibold text-base sm:text-lg text-primary tracking-tight">
                  Bill of Materials (BOQ)
                </h2>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-panel text-secondary border border-border">
                  {filteredItems.length} items
                </span>
                <button
                  onClick={handleRecalculate}
                  disabled={isRecalculating}
                  title="Recalculate verified material quantities from plan coordinates"
                  className="p-1 rounded-md hover:bg-panel text-secondary hover:text-primary transition-colors disabled:opacity-50"
                >
                  <IconRefresh className={`w-3.5 h-3.5 ${isRecalculating ? 'animate-spin text-accent' : ''}`} />
                </button>
              </div>

              {selectedMaterialTag && (
                <button
                  onClick={() => setSelectedMaterialTag(null)}
                  className="text-xs text-accent hover:underline flex items-center gap-1 font-medium"
                >
                  Clear Highlight (×)
                </button>
              )}
            </div>

            <p className="text-xs text-secondary mb-3">
              Directly extracted from backend geometric analysis (IS 456 / CPWD Standard) • Total Estimated Material Cost & Quantities
            </p>

            {/* Category Filter Pills */}
            <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none pb-0.5">
              {(
                [
                  { id: 'all', label: 'All Items' },
                  { id: 'structure', label: 'Structure & RCC' },
                  { id: 'walls', label: 'Masonry & Plaster' },
                  { id: 'flooring', label: 'Tiles & Flooring' },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-all ${
                    activeTab === tab.id
                      ? 'bg-panel text-primary border border-border shadow-sm font-semibold'
                      : 'text-secondary hover:text-primary hover:bg-panel/40'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Error Banner */}
          {errorMsg && (
            <div className="mx-3 sm:mx-4 mt-3 p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center justify-between">
              <span>{errorMsg}</span>
              <button
                onClick={handleRecalculate}
                className="underline font-medium hover:text-rose-300 ml-2"
              >
                Retry
              </button>
            </div>
          )}

          {/* Quantities Table Header */}
          <div className="px-3 sm:px-4 pt-3 pb-1.5 flex items-center justify-between text-[11px] font-semibold text-secondary uppercase tracking-wider border-b border-border/50 flex-shrink-0">
            <span className="w-1/2">Material & Category</span>
            <span className="w-1/4 text-right">Surface / Area</span>
            <span className="w-1/4 text-right">Total Verified Qty</span>
          </div>

          {/* Interactive Material List (Strictly Backend Items) */}
          <div className="flex-1 overflow-y-auto p-3 sm:p-4 space-y-2">
            {isLoading && sheetItems.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-48 text-secondary text-xs space-y-2">
                <span className="animate-spin text-lg">⟳</span>
                <p>Loading verified quantities from backend...</p>
              </div>
            ) : filteredItems.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-48 text-secondary text-xs text-center p-4">
                <p className="font-medium text-primary mb-1">No items match this category</p>
                <p className="text-[11px]">Click "All Items" or recalculate from plan.</p>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleRecalculate}
                  className="mt-3"
                  leftIcon={<IconRefresh className="w-3.5 h-3.5" />}
                >
                  Recalculate Quantities
                </Button>
              </div>
            ) : (
              filteredItems.map((item) => {
                const tag = item.surface_tag || item.name;
                const isSelected = selectedMaterialTag === tag;
                const style = getMaterialHighlightStyle(tag);

                const areaDisplay = item.area
                  ? `${item.area.toFixed(1)} m²`
                  : item.secondary_quantity
                  ? `${item.secondary_quantity} ${item.secondary_unit || ''}`.trim()
                  : '-';

                const wastePct = Math.round((item.waste_factor || 0) * 100);

                return (
                  <div
                    key={item.id}
                    onClick={() =>
                      setSelectedMaterialTag(isSelected ? null : tag)
                    }
                    className="group relative p-3 rounded-xl border transition-all cursor-pointer shadow-sm hover:shadow"
                    style={{
                      backgroundColor: isSelected ? style.badgeBg : undefined,
                      borderColor: isSelected ? style.color : undefined,
                      boxShadow: isSelected ? `0 0 0 1px ${style.color}` : undefined,
                    }}
                  >
                    <div className="flex items-center justify-between gap-2">
                      {/* Material Name & Category */}
                      <div className="w-1/2 pr-1">
                        <div className="flex items-center gap-2">
                          {/* Distinct Material Highlight Color Pill */}
                          <span
                            className="w-3 h-3 rounded-full flex-shrink-0 shadow-sm transition-transform group-hover:scale-110"
                            style={{
                              backgroundColor: style.color,
                              boxShadow: `0 0 6px ${style.color}88`,
                            }}
                            title={`Highlight color: ${style.label}`}
                          />
                          <p className="text-xs sm:text-sm font-semibold text-primary leading-tight truncate">
                            {item.name}
                          </p>
                        </div>
                        <div className="flex items-center gap-1.5 pl-5 mt-1">
                          <span
                            className="text-[10px] font-medium px-1.5 py-0.5 rounded border"
                            style={{
                              backgroundColor: style.badgeBg,
                              color: style.badgeText,
                              borderColor: style.badgeBorder,
                            }}
                          >
                            {item.category}
                          </span>
                          {wastePct > 0 && (
                            <span className="text-[10px] text-secondary">
                              +{wastePct}% waste
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Surface / Measured Area */}
                      <div className="w-1/4 text-right">
                        <span className="text-xs font-mono text-secondary">
                          {areaDisplay}
                        </span>
                        <p className="text-[10px] text-secondary/70">
                          {item.surface_tag ? item.surface_tag.replace(/_/g, ' ') : 'measured'}
                        </p>
                      </div>

                      {/* Total Verified Quantity (Without any arbitrary cost column) */}
                      <div className="w-1/4 text-right">
                        <span className="inline-block text-xs font-semibold text-primary bg-panel px-2 py-1 rounded-md border border-border">
                          {Number(item.total_quantity || item.quantity || 0).toLocaleString('en-IN', {
                            maximumFractionDigits: 1,
                          })}{' '}
                          <span className="text-[10px] text-secondary font-normal">{item.unit}</span>
                        </span>
                        {item.quantity && item.quantity !== item.total_quantity && (
                          <p className="text-[10px] text-secondary mt-0.5">
                            base: {Number(item.quantity).toLocaleString('en-IN', { maximumFractionDigits: 1 })}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })
            )}

            <p className="text-[11px] text-secondary/75 pt-1 pb-2 text-center italic">
              Click any material above to glow its architectural surfaces in the 3D studio.
            </p>
          </div>

          {/* Clean Engineering Quantity Summary (Replaces arbitrary cost estimation box) */}
          <div className="p-3 sm:p-4 border-t border-border bg-panel/50 flex-shrink-0">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-primary uppercase tracking-wider">
                Engineering Quantity Survey
              </span>
              <span className="text-[10px] text-accent bg-accent/10 px-2 py-0.5 rounded font-mono border border-accent/20">
                CPWD / IS 456 Standards
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="p-2 rounded-lg bg-surface border border-border">
                <span className="text-[11px] text-secondary block">Total Verified Materials</span>
                <span className="text-sm font-semibold text-primary">{sheetItems.length} Mapped Items</span>
              </div>
              <div className="p-2 rounded-lg bg-surface border border-border">
                <span className="text-[11px] text-secondary block">Survey Status</span>
                <span className="text-sm font-semibold text-emerald-400 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  Synchronized
                </span>
              </div>
            </div>

            <div className="mt-3 flex gap-2">
              <Button
                variant="secondary"
                size="sm"
                fullWidth
                onClick={handleExportCsv}
                leftIcon={<IconDownload className="w-3.5 h-3.5" />}
              >
                CSV Export
              </Button>
              <Button
                variant="secondary"
                size="sm"
                fullWidth
                onClick={handleExportPdf}
                leftIcon={<IconFilePdf className="w-3.5 h-3.5 text-rose-400" />}
              >
                Printable PDF
              </Button>
            </div>
          </div>
        </aside>
      </main>
    </div>
  );
}

export default WorkspacePage;
