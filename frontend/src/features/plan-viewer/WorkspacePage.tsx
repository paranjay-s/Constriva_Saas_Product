import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProject } from '../../context/ProjectContext';
import { PlanViewer } from './PlanViewer';
import { Button } from '../../components/ui/Button';
import {
  IconArrowLeft,
  IconArrowRight,
  IconCheck,
  IconDownload,
} from '../../components/ui/Icons';

export function WorkspacePage() {
  const navigate = useNavigate();
  const {
    activeProject,
    materials,
    selectedMaterialTag,
    setSelectedMaterialTag,
  } = useProject();

  const [activeTab, setActiveTab] = useState<'all' | 'flooring' | 'walls' | 'structure'>('all');
  const [downloadSuccess, setDownloadSuccess] = useState(false);

  // Filter materials based on category tab
  const filteredMaterials = materials.filter((item) => {
    if (activeTab === 'all') return true;
    if (activeTab === 'flooring') return item.category.toLowerCase().includes('flooring');
    if (activeTab === 'walls') return item.category.toLowerCase().includes('paint') || item.category.toLowerCase().includes('wall');
    if (activeTab === 'structure') return item.category.toLowerCase().includes('masonry') || item.category.toLowerCase().includes('structural');
    return true;
  });

  // Calculate totals
  const subtotal = materials.reduce((acc, item) => acc + item.estimatedAmount, 0);
  const contingency = Math.round(subtotal * 0.05);
  const totalCost = subtotal + contingency;

  const handleExportEstimate = () => {
    const csvContent =
      'Material Name,Category,Measurement,Quantity,Rate (INR),Amount (INR)\n' +
      materials
        .map(
          (m) =>
            `"${m.materialName}","${m.category}","${m.totalArea}","${m.quantity}",${m.rate},${m.estimatedAmount}`
        )
        .join('\n') +
      `\n\nSubtotal,,,,,${subtotal}\nContingency (5%),,,,,${contingency}\nTotal Estimated Cost,,,,,${totalCost}`;

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `${activeProject?.name || 'project'}_materials_estimate.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    setDownloadSuccess(true);
    setTimeout(() => setDownloadSuccess(false), 3000);
  };

  return (
    <div className="min-h-screen bg-canvas text-primary flex flex-col">
      {/* Top Project Sub-header */}
      <header className="border-b border-border bg-surface/70 backdrop-blur-md px-4 sm:px-6 py-3 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/projects/options')}
            leftIcon={<IconArrowLeft className="w-4 h-4" />}
          >
            Options
          </Button>

          <div className="h-4 w-px bg-border" />

          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-serif font-medium text-primary text-base sm:text-lg tracking-tight">
                {activeProject?.name || 'Pavilion Serena Residences'}
              </h1>
              <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-accent/15 text-accent border border-accent/30">
                {activeProject?.type || 'Residential'}
              </span>
              <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                3D Model Active
              </span>
            </div>
            <p className="text-xs text-secondary hidden sm:block">
              Parsed from architectural blueprint • 5 identified zones • Real-time material mapping
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={handleExportEstimate}
            leftIcon={downloadSuccess ? <IconCheck className="w-3.5 h-3.5 text-emerald-400" /> : <IconDownload className="w-3.5 h-3.5" />}
          >
            {downloadSuccess ? 'Downloaded CSV' : 'Export BOQ'}
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={() => navigate('/projects/loan-analysis')}
            rightIcon={<IconArrowRight className="w-4 h-4" />}
          >
            Compare with Loan
          </Button>
        </div>
      </header>

      {/* Main Split Layout: 65% 3D Viewer / 35% Material Estimation Table */}
      <main className="flex-1 flex flex-col lg:flex-row overflow-hidden min-h-[calc(100vh-125px)]">
        {/* Left Side: 3D Viewport (65% on desktop) */}
        <section className="lg:w-[63%] xl:w-[65%] p-3 sm:p-4 flex flex-col min-h-[500px] lg:min-h-0">
          <div className="flex-1 w-full h-full">
            <PlanViewer />
          </div>
        </section>

        {/* Right Side: Material Estimate & Cost Breakdown (35% on desktop) */}
        <aside className="lg:w-[37%] xl:w-[35%] border-t lg:border-t-0 lg:border-l border-border bg-surface flex flex-col overflow-y-auto max-h-[calc(100vh-125px)]">
          {/* Section Header */}
          <div className="p-4 sm:p-5 border-b border-border bg-surface sticky top-0 z-10">
            <div className="flex items-center justify-between mb-2">
              <div>
                <h2 className="font-serif font-semibold text-lg text-primary tracking-tight">
                  Bill of Materials (BOQ)
                </h2>
                <p className="text-xs text-secondary">
                  Extracted from floor plan geometric coordinates
                </p>
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

            {/* Category Filter Tabs */}
            <div className="flex items-center gap-1.5 pt-2 overflow-x-auto scrollbar-none">
              {(
                [
                  { id: 'all', label: 'All Items' },
                  { id: 'flooring', label: 'Flooring' },
                  { id: 'walls', label: 'Walls & Finish' },
                  { id: 'structure', label: 'Structure' },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
                    activeTab === tab.id
                      ? 'bg-panel text-primary border border-border shadow-sm'
                      : 'text-secondary hover:text-primary hover:bg-panel/50'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Interactive Material Quantities Table (3 columns) */}
          <div className="p-4 sm:p-5 flex-1">
            <div className="flex items-center justify-between text-xs text-secondary font-medium px-2 pb-2">
              <span className="w-1/2">Material & Surface</span>
              <span className="w-1/4 text-right">Total Area</span>
              <span className="w-1/4 text-right">Quantity</span>
            </div>

            <div className="space-y-1.5">
              {filteredMaterials.map((item) => {
                const isSelected = selectedMaterialTag === item.surfaceTag;

                return (
                  <div
                    key={item.id}
                    onClick={() =>
                      setSelectedMaterialTag(isSelected ? null : item.surfaceTag)
                    }
                    className={`group relative p-3 rounded-lg border transition-all cursor-pointer ${
                      isSelected
                        ? 'bg-accent/10 border-accent/60 shadow-md ring-1 ring-accent/30'
                        : 'bg-panel/60 border-border hover:border-border-hover hover:bg-panel'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      {/* Material Name & Category */}
                      <div className="w-1/2 pr-2">
                        <div className="flex items-center gap-2">
                          <span
                            className={`w-2 h-2 rounded-full flex-shrink-0 ${
                              item.surfaceTag === 'wood'
                                ? 'bg-amber-600'
                                : item.surfaceTag === 'marble'
                                ? 'bg-zinc-200'
                                : item.surfaceTag === 'tiles'
                                ? 'bg-sky-400'
                                : item.surfaceTag === 'paint'
                                ? 'bg-rose-300'
                                : 'bg-zinc-400'
                            }`}
                          />
                          <p className="text-sm font-medium text-primary leading-tight">
                            {item.materialName}
                          </p>
                        </div>
                        <p className="text-[11px] text-secondary pl-4 mt-0.5">
                          {item.category}
                        </p>
                      </div>

                      {/* Total Area */}
                      <div className="w-1/4 text-right">
                        <span className="text-xs font-mono text-secondary">
                          {item.totalArea}
                        </span>
                      </div>

                      {/* Quantity */}
                      <div className="w-1/4 text-right">
                        <span className="text-xs font-medium text-primary bg-surface px-2 py-0.5 rounded border border-border">
                          {item.quantity}
                        </span>
                      </div>
                    </div>

                    {/* Hint on hover */}
                    <div className="mt-2 pt-2 border-t border-border/50 flex items-center justify-between text-[11px] text-secondary">
                      <span>Rate: ₹{item.rate.toLocaleString('en-IN')}/{item.unit}</span>
                      <span className="text-primary font-mono font-medium">
                        ₹{item.estimatedAmount.toLocaleString('en-IN')}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            <p className="text-[11px] text-secondary/80 mt-3 text-center italic">
              Click any material card above to highlight its physical location in the 3D viewport.
            </p>
          </div>

          {/* Cost Summary Section (Separated as required by product spec) */}
          <div className="p-4 sm:p-5 border-t border-border bg-panel/40">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-medium text-secondary uppercase tracking-wider">
                Cost Valuation
              </span>
              <span className="text-xs text-accent bg-accent/10 px-2 py-0.5 rounded font-mono">
                CPWD / Indian Market Rates 2026
              </span>
            </div>

            <div className="space-y-2 text-xs">
              <div className="flex justify-between text-secondary">
                <span>Material Subtotal</span>
                <span className="font-mono text-primary">₹{subtotal.toLocaleString('en-IN')}</span>
              </div>
              <div className="flex justify-between text-secondary">
                <span>Wastage & Handling Allowance (5%)</span>
                <span className="font-mono text-primary">₹{contingency.toLocaleString('en-IN')}</span>
              </div>
              <div className="h-px bg-border my-2" />
              <div className="flex justify-between items-baseline pt-1">
                <div>
                  <span className="text-sm font-medium text-primary block">
                    Total Estimated Material Cost
                  </span>
                  <span className="text-[11px] text-secondary">
                    Excludes civil labor and permits
                  </span>
                </div>
                <div className="text-right">
                  <span className="font-serif text-xl sm:text-2xl font-bold text-accent tracking-tight">
                    ₹{totalCost.toLocaleString('en-IN')}
                  </span>
                </div>
              </div>
            </div>

            {/* Primary Action Button */}
            <div className="mt-5">
              <Button
                variant="primary"
                fullWidth
                size="lg"
                onClick={() => navigate('/projects/loan-analysis')}
                rightIcon={<IconArrowRight className="w-4 h-4" />}
              >
                Compare with Loan Sanction
              </Button>
            </div>
          </div>
        </aside>
      </main>
    </div>
  );
}
export default WorkspacePage;
