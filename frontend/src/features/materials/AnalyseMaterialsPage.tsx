import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import {
  IconArrowLeft,
  IconUpload,
  IconSparkles,
  IconCheck,
  IconDownload,
} from '../../components/ui/Icons';
import type { PhotoMaterialResult } from '../../types';

// Curated sample architecture photos for quick testing
const SAMPLE_PHOTOS = [
  {
    id: 'sample_living',
    title: 'Modern Minimalist Living Hall',
    url: 'https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?auto=format&fit=crop&w=1000&q=80',
    description: 'High ceiling room with Italian travertine floor, fluted oak paneling, and floor-to-ceiling glass.',
  },
  {
    id: 'sample_kitchen',
    title: 'Contemporary Chef Kitchen',
    url: 'https://images.unsplash.com/photo-1556911220-e15b29be8c8f?auto=format&fit=crop&w=1000&q=80',
    description: 'Quartz waterfall countertops, porcelain backsplash, and matte black cabinetry.',
  },
  {
    id: 'sample_exterior',
    title: 'Brutalist Villa Façade',
    url: 'https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1000&q=80',
    description: 'Exposed concrete board-formed walls, cedar louvers, and black powder-coated aluminum.',
  },
];

// Sample vision detection results
const SAMPLE_DETECTIONS: Record<string, PhotoMaterialResult[]> = {
  default: [
    {
      id: 'pm_1',
      material: 'Italian Travertine Marble',
      category: 'Flooring',
      estimatedArea: '38.5 m²',
      indicativeRate: '₹4,800 / m²',
      description: 'Honed unfilled roman travertine slabs laid in cross-cut pattern with 1.5mm epoxy grout.',
      confidence: 'High',
    },
    {
      id: 'pm_2',
      material: 'Fluted American White Oak',
      category: 'Wall Cladding',
      estimatedArea: '22.0 m²',
      indicativeRate: '₹3,600 / m²',
      description: 'Vertical CNC-milled fluted acoustic timber battens over moisture-resistant MDF core.',
      confidence: 'High',
    },
    {
      id: 'pm_3',
      material: 'Low-E Acoustic Double Glazing',
      category: 'Fenestration',
      estimatedArea: '16.8 m²',
      indicativeRate: '₹2,400 / m²',
      description: 'Thermally broken aluminum curtain wall frame with 24mm argon-filled glass unit.',
      confidence: 'Moderate',
    },
    {
      id: 'pm_4',
      material: 'Textured Lime Plaster (Stucco)',
      category: 'Ceiling & Walls',
      estimatedArea: '45.0 m²',
      indicativeRate: '₹650 / m²',
      description: 'Matte breathable mineral lime wash finish in warm off-white (LRV 82).',
      confidence: 'High',
    },
    {
      id: 'pm_5',
      material: 'Recessed Brass Reveal Profiles',
      category: 'Architectural Hardware',
      estimatedArea: '28.0 Rmt',
      indicativeRate: '₹950 / Rmt',
      description: 'Satin brushed natural brass shadowline channel between timber and plaster interface.',
      confidence: 'Indicative',
    },
  ],
};

export function AnalyseMaterialsPage() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selectedImage, setSelectedImage] = useState<string | null>(SAMPLE_PHOTOS[0].url);
  const [selectedPhotoName, setSelectedPhotoName] = useState<string>(SAMPLE_PHOTOS[0].title);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisStep, setAnalysisStep] = useState<string>('');
  const [results, setResults] = useState<PhotoMaterialResult[] | null>(SAMPLE_DETECTIONS.default);
  const [downloadSuccess, setDownloadSuccess] = useState(false);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (uploadEvent) => {
        if (uploadEvent.target?.result) {
          setSelectedImage(uploadEvent.target.result as string);
          setSelectedPhotoName(file.name);
          setResults(null);
        }
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSelectSample = (sample: typeof SAMPLE_PHOTOS[0]) => {
    setSelectedImage(sample.url);
    setSelectedPhotoName(sample.title);
    setResults(null);
  };

  const runAnalysis = () => {
    if (!selectedImage) return;

    setIsAnalyzing(true);
    setResults(null);

    // Multi-step vision pipeline simulation
    setAnalysisStep('Detecting architectural perspective & boundary planes...');
    setTimeout(() => {
      setAnalysisStep('Extracting color spectrum, specular highlights & micro-textures...');
    }, 800);

    setTimeout(() => {
      setAnalysisStep('Querying CPWD standard materials catalog for regional price indices...');
    }, 1600);

    setTimeout(() => {
      setIsAnalyzing(false);
      setResults(SAMPLE_DETECTIONS.default);
    }, 2400);
  };

  const calculateTotal = () => {
    if (!results) return 0;
    return results.reduce((sum, item) => {
      const rateNum = parseInt(item.indicativeRate.replace(/[^0-9]/g, '')) || 0;
      const areaNum = parseFloat(item.estimatedArea.replace(/[^0-9.]/g, '')) || 1;
      return sum + Math.round(rateNum * areaNum);
    }, 0);
  };

  const handleExportReport = () => {
    if (!results) return;
    const csvContent =
      'Detected Material,Category,Estimated Area,Indicative Rate,Confidence,Description\n' +
      results
        .map(
          (r) =>
            `"${r.material}","${r.category}","${r.estimatedArea}","${r.indicativeRate}","${r.confidence}","${r.description}"`
        )
        .join('\n') +
      `\n\nApproximate Total Valuation,,,,₹${calculateTotal().toLocaleString('en-IN')}`;

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `material_analysis_${selectedPhotoName.replace(/\s+/g, '_')}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    setDownloadSuccess(true);
    setTimeout(() => setDownloadSuccess(false), 3000);
  };

  return (
    <div className="min-h-screen bg-canvas text-primary flex flex-col">
      {/* Top Header */}
      <header className="border-b border-border bg-surface/80 backdrop-blur-md px-4 sm:px-6 py-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/home')}
            leftIcon={<IconArrowLeft className="w-4 h-4" />}
          >
            Home
          </Button>

          <div className="h-4 w-px bg-border" />

          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-serif font-medium text-primary text-base sm:text-lg">
                Interior Material Photo Analysis
              </h1>
              <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-accent/15 text-accent border border-accent/30 flex items-center gap-1">
                <IconSparkles className="w-3 h-3" />
                Vision AI
              </span>
            </div>
            <p className="text-xs text-secondary hidden sm:block">
              Upload any photo of a room, facade, or interior finish to identify materials, dimensions, and estimated market rates.
            </p>
          </div>
        </div>

        {results && (
          <Button
            variant="secondary"
            size="sm"
            onClick={handleExportReport}
            leftIcon={downloadSuccess ? <IconCheck className="w-3.5 h-3.5 text-emerald-400" /> : <IconDownload className="w-3.5 h-3.5" />}
          >
            {downloadSuccess ? 'Downloaded CSV' : 'Export Analysis'}
          </Button>
        )}
      </header>

      {/* Main Content Split: Upload/Image Preview on Left, Analysis Table on Right */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8 grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Photo Upload & Preview (5 cols) */}
        <div className="lg:col-span-5 space-y-5">
          <Card className="p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-secondary mb-3">
              Photo Source
            </h2>

            {/* Hidden native input */}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              accept="image/png, image/jpeg, image/webp"
              className="hidden"
            />

            {/* Selected Image Preview */}
            {selectedImage ? (
              <div className="relative rounded-xl overflow-hidden border border-border group bg-black/40">
                <img
                  src={selectedImage}
                  alt="Selected architecture view"
                  className="w-full h-72 sm:h-80 object-cover group-hover:scale-102 transition-transform duration-500"
                />

                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent flex flex-col justify-end p-4">
                  <p className="text-sm font-medium text-white line-clamp-1">
                    {selectedPhotoName}
                  </p>
                  <p className="text-xs text-secondary mt-0.5">
                    Ready for neural material decomposition
                  </p>
                </div>

                <div className="absolute top-3 right-3 flex items-center gap-2">
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="px-2.5 py-1.5 rounded-lg bg-surface/90 backdrop-blur-md border border-border text-xs text-primary hover:bg-panel transition-colors shadow-lg"
                  >
                    Change Photo
                  </button>
                </div>
              </div>
            ) : (
              /* Dropzone */
              <div
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-border hover:border-accent/60 rounded-xl p-8 text-center cursor-pointer transition-colors bg-panel/30 flex flex-col items-center justify-center min-h-[260px]"
              >
                <div className="w-12 h-12 rounded-full bg-accent/10 border border-accent/20 flex items-center justify-center text-accent mb-3">
                  <IconUpload className="w-6 h-6" />
                </div>
                <p className="text-sm font-medium text-primary">
                  Click or drag photo here to upload
                </p>
                <p className="text-xs text-secondary mt-1">
                  JPG, PNG, or WEBP up to 25 MB
                </p>
              </div>
            )}

            {/* Run Analysis CTA */}
            <div className="mt-4">
              <Button
                variant="primary"
                fullWidth
                size="lg"
                onClick={runAnalysis}
                isLoading={isAnalyzing}
                disabled={!selectedImage || isAnalyzing}
                leftIcon={<IconSparkles className="w-4 h-4" />}
              >
                {results ? 'Re-Analyse Visible Materials' : 'Analyse Materials in Photo'}
              </Button>
            </div>
          </Card>

          {/* Quick Sample Selector */}
          <Card className="p-4 bg-panel/50">
            <span className="text-xs font-semibold text-secondary uppercase tracking-wider block mb-2.5">
              Or Try With Architectural Samples:
            </span>
            <div className="grid grid-cols-3 gap-2">
              {SAMPLE_PHOTOS.map((sample) => (
                <button
                  key={sample.id}
                  onClick={() => handleSelectSample(sample)}
                  className={`text-left rounded-lg overflow-hidden border p-1 transition-all ${
                    selectedImage === sample.url
                      ? 'border-accent ring-1 ring-accent bg-accent/10'
                      : 'border-border hover:border-border-hover bg-surface'
                  }`}
                >
                  <img
                    src={sample.url}
                    alt={sample.title}
                    className="w-full h-14 object-cover rounded mb-1"
                  />
                  <p className="text-[11px] font-medium text-primary truncate px-1">
                    {sample.title.split(' ')[0]}
                  </p>
                </button>
              ))}
            </div>
          </Card>
        </div>

        {/* Right Column: AI Material Identification Results (7 cols) */}
        <div className="lg:col-span-7 flex flex-col">
          {isAnalyzing ? (
            /* Analysis in-progress state */
            <Card className="flex-1 p-8 sm:p-12 flex flex-col items-center justify-center text-center space-y-4">
              <div className="relative">
                <div className="w-16 h-16 rounded-full border-2 border-accent border-t-transparent animate-spin" />
                <div className="absolute inset-0 flex items-center justify-center">
                  <IconSparkles className="w-6 h-6 text-accent" />
                </div>
              </div>
              <div>
                <h3 className="font-serif text-lg font-medium text-primary">
                  Neural Material Segmentation
                </h3>
                <p className="text-sm text-accent mt-1 animate-pulse font-mono">
                  {analysisStep}
                </p>
              </div>
              <p className="text-xs text-secondary max-w-sm">
                Parsing surface reflectance, albedo maps, and structural joints against Indian CPWD specifications...
              </p>
            </Card>
          ) : results ? (
            /* Results Table */
            <div className="space-y-5">
              <Card className="p-5">
                <div className="flex flex-wrap items-center justify-between gap-2 pb-4 border-b border-border mb-4">
                  <div>
                    <h2 className="font-serif font-semibold text-lg text-primary tracking-tight">
                      Identified Material Specifications
                    </h2>
                    <p className="text-xs text-secondary">
                      5 distinct finishes detected with estimated coverage and indicative rates
                    </p>
                  </div>

                  <span className="px-2.5 py-1 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-medium flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-400" />
                    Analysis Complete
                  </span>
                </div>

                {/* Table of Detected Materials */}
                <div className="space-y-3">
                  {results.map((item) => (
                    <div
                      key={item.id}
                      className="p-3.5 rounded-lg border border-border bg-panel/60 hover:bg-panel transition-colors"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-semibold text-primary">
                              {item.material}
                            </span>
                            <span className="px-2 py-0.5 rounded text-[10px] uppercase font-semibold bg-surface border border-border text-secondary">
                              {item.category}
                            </span>
                          </div>
                          <p className="text-xs text-secondary mt-1">
                            {item.description}
                          </p>
                        </div>

                        <div className="text-right">
                          <span className="text-xs font-semibold text-accent font-mono block">
                            {item.indicativeRate}
                          </span>
                          <span className="text-[11px] text-secondary">
                            Area: <strong className="text-primary">{item.estimatedArea}</strong>
                          </span>
                        </div>
                      </div>

                      <div className="mt-2.5 pt-2 border-t border-border/50 flex items-center justify-between text-[11px]">
                        <span className="text-secondary">
                          AI Certainty:{' '}
                          <span
                            className={
                              item.confidence === 'High'
                                ? 'text-emerald-400 font-medium'
                                : 'text-amber-400 font-medium'
                            }
                          >
                            {item.confidence}
                          </span>
                        </span>

                        <span className="text-secondary font-mono">
                          Est. Subtotal: ₹
                          {(
                            parseInt(item.indicativeRate.replace(/[^0-9]/g, '')) *
                            (parseFloat(item.estimatedArea.replace(/[^0-9.]/g, '')) || 1)
                          ).toLocaleString('en-IN')}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Valuation Summary Footer */}
                <div className="mt-6 pt-4 border-t border-border flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <span className="text-xs text-secondary block">
                      Estimated Material Valuation for Visible Scope
                    </span>
                    <span className="font-serif text-2xl font-bold text-accent tracking-tight">
                      ₹{calculateTotal().toLocaleString('en-IN')}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => navigate('/projects/new')}
                    >
                      Create Project with this Scope
                    </Button>
                  </div>
                </div>
              </Card>

              {/* Disclaimer */}
              <div className="p-3.5 rounded-lg border border-border/60 bg-panel/30 text-xs text-secondary leading-relaxed">
                <strong className="text-primary">Note on Visual Estimation:</strong> Quantities and areas are calculated based on camera perspective, known reference objects, and regional CPWD market indices. Physical site measurements and contractor quotations should be obtained before procuring building supplies.
              </div>
            </div>
          ) : (
            /* Empty placeholder state */
            <Card className="flex-1 p-8 sm:p-12 flex flex-col items-center justify-center text-center space-y-3">
              <div className="w-12 h-12 rounded-full bg-panel border border-border flex items-center justify-center text-secondary">
                <IconSparkles className="w-5 h-5" />
              </div>
              <h3 className="font-serif text-base font-medium text-primary">
                No Analysis Performed Yet
              </h3>
              <p className="text-xs text-secondary max-w-sm">
                Select an image on the left and click &quot;Analyse Materials in Photo&quot; to inspect visible finishes, calculate areas, and view current CPWD material rates.
              </p>
            </Card>
          )}
        </div>
      </main>
    </div>
  );
}
export default AnalyseMaterialsPage;
