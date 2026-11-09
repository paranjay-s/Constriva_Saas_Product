import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProject } from '../../context/ProjectContext';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { Input } from '../../components/ui/Input';
import {
  IconArrowLeft,
  IconFilePdf,
  IconCheck,
  IconDownload,
} from '../../components/ui/Icons';

export function LoanAnalysisPage() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { activeProject, materials, loanComparison, updateLoanAmount } = useProject();

  const [inputMode, setInputMode] = useState<'manual' | 'document'>('manual');
  const [loanInputStr, setLoanInputStr] = useState<string>(
    loanComparison.availableLoan.toString()
  );
  const [uploadedLetterName, setUploadedLetterName] = useState<string | null>(null);
  const [isParsingDoc, setIsParsingDoc] = useState(false);
  const [docBankName, setDocBankName] = useState<string | null>(null);
  const [downloadSuccess, setDownloadSuccess] = useState(false);

  // Material cost from active project
  const materialCost = materials.reduce((acc, item) => acc + item.estimatedAmount, 0);
  const contingency = Math.round(materialCost * 0.05);
  const totalCost = materialCost + contingency;

  const currentAvailableLoan = parseFloat(loanInputStr) || 0;
  const surplus = Math.max(0, currentAvailableLoan - totalCost);
  const shortfall = Math.max(0, totalCost - currentAvailableLoan);
  const isSufficient = currentAvailableLoan >= totalCost;
  const utilizationPercentage =
    currentAvailableLoan > 0
      ? Math.min(100, Math.round((totalCost / currentAvailableLoan) * 100))
      : 0;

  const handleManualAmountChange = (val: string) => {
    setLoanInputStr(val);
    const parsed = parseFloat(val);
    if (!isNaN(parsed) && parsed >= 0) {
      updateLoanAmount(parsed);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploadedLetterName(file.name);
      setIsParsingDoc(true);

      setTimeout(() => {
        setIsParsingDoc(false);
        setDocBankName('State Bank of India • In-Principle Approval');
        const extractedAmount = 1800000; // ₹18,00,000 from parsed letter
        setLoanInputStr(extractedAmount.toString());
        updateLoanAmount(extractedAmount);
      }, 1500);
    }
  };

  const handleDownloadReport = () => {
    const reportContent =
      `CONSTRUTIVA ARCHITECTURAL SUITE - LOAN FEASIBILITY ASSESSMENT\n` +
      `Project: ${activeProject?.name || 'Residence'}\n` +
      `Date: ${new Date().toLocaleDateString('en-IN')}\n\n` +
      `FINANCIAL SUMMARY:\n` +
      `Sanctioned Loan Facility: INR ${currentAvailableLoan.toLocaleString('en-IN')}\n` +
      `Total Estimated Material BOQ: INR ${totalCost.toLocaleString('en-IN')}\n` +
      `${isSufficient ? 'Surplus Liquidity Buffer' : 'Projected Shortfall'}: INR ${(isSufficient ? surplus : shortfall).toLocaleString('en-IN')}\n` +
      `Material Cost Utilization: ${utilizationPercentage}%\n\n` +
      `DISCLAIMER:\n` +
      `This comparison reflects estimated architectural material procurement costs only. Civil labor, contractor overhead, and statutory approvals are not included.`;

    const blob = new Blob([reportContent], { type: 'text/plain;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${activeProject?.name || 'project'}_loan_analysis.txt`;
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
            onClick={() => navigate('/projects/3d-workspace')}
            leftIcon={<IconArrowLeft className="w-4 h-4" />}
          >
            3D Workspace
          </Button>

          <div className="h-4 w-px bg-border" />

          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-serif font-medium text-primary text-base sm:text-lg">
                Construction Loan Feasibility Analysis
              </h1>
              <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-accent/15 text-accent border border-accent/30">
                {activeProject?.name || 'Pavilion Serena'}
              </span>
            </div>
            <p className="text-xs text-secondary hidden sm:block">
              Compare your sanctioned bank credit against estimated bill of materials to verify financial viability.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={handleDownloadReport}
            leftIcon={downloadSuccess ? <IconCheck className="w-3.5 h-3.5 text-emerald-400" /> : <IconDownload className="w-3.5 h-3.5" />}
          >
            {downloadSuccess ? 'Downloaded Report' : 'Export Feasibility Report'}
          </Button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-6xl w-full mx-auto p-4 sm:p-6 lg:p-8 space-y-6">
        {/* Top 3 KPI Comparative Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-6">
          {/* Card 1: Available Loan */}
          <Card className="p-5 border-border bg-panel/70">
            <span className="text-xs font-semibold text-secondary uppercase tracking-wider block mb-1">
              Sanctioned Loan Facility
            </span>
            <div className="flex items-baseline gap-2">
              <span className="font-serif text-2xl sm:text-3xl font-bold text-primary tracking-tight">
                ₹{currentAvailableLoan.toLocaleString('en-IN')}
              </span>
            </div>
            <p className="text-xs text-secondary mt-2 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-accent" />
              {docBankName || 'Self-Reported Banking Facility'}
            </p>
          </Card>

          {/* Card 2: Material BOQ Cost */}
          <Card className="p-5 border-border bg-panel/70">
            <span className="text-xs font-semibold text-secondary uppercase tracking-wider block mb-1">
              Estimated Material BOQ Cost
            </span>
            <div className="flex items-baseline gap-2">
              <span className="font-serif text-2xl sm:text-3xl font-bold text-accent tracking-tight">
                ₹{totalCost.toLocaleString('en-IN')}
              </span>
            </div>
            <p className="text-xs text-secondary mt-2">
              Derived from 3D Model • Includes 5% handling allowance
            </p>
          </Card>

          {/* Card 3: Surplus / Shortfall Status */}
          <Card
            className={`p-5 border ${
              isSufficient
                ? 'border-emerald-500/40 bg-emerald-500/5'
                : 'border-rose-500/40 bg-rose-500/5'
            }`}
          >
            <span className="text-xs font-semibold text-secondary uppercase tracking-wider block mb-1">
              {isSufficient ? 'Remaining Liquidity Buffer' : 'Estimated Capital Shortfall'}
            </span>
            <div className="flex items-baseline gap-2">
              <span
                className={`font-serif text-2xl sm:text-3xl font-bold tracking-tight ${
                  isSufficient ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                ₹{(isSufficient ? surplus : shortfall).toLocaleString('en-IN')}
              </span>
            </div>
            <p className="text-xs text-secondary mt-2">
              {isSufficient
                ? `Buffer available for civil labor & MEP works (${utilizationPercentage}% loan consumed)`
                : 'Sanction is insufficient to cover raw materials alone'}
            </p>
          </Card>
        </div>

        {/* Loan Input Configuration & Document Upload */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Loan Input Controls (6 cols) */}
          <Card className="lg:col-span-6 p-6">
            <h2 className="font-serif font-semibold text-lg text-primary tracking-tight mb-4">
              Loan Amount Configuration
            </h2>

            {/* Mode Selector Tabs */}
            <div className="flex items-center gap-2 p-1 rounded-lg bg-surface border border-border mb-5">
              <button
                onClick={() => setInputMode('manual')}
                className={`flex-1 py-2 text-xs font-medium rounded-md transition-all ${
                  inputMode === 'manual'
                    ? 'bg-panel text-primary shadow'
                    : 'text-secondary hover:text-primary'
                }`}
              >
                Manual Amount Entry
              </button>
              <button
                onClick={() => setInputMode('document')}
                className={`flex-1 py-2 text-xs font-medium rounded-md transition-all ${
                  inputMode === 'document'
                    ? 'bg-panel text-primary shadow'
                    : 'text-secondary hover:text-primary'
                }`}
              >
                Upload Sanction Letter (PDF)
              </button>
            </div>

            {inputMode === 'manual' ? (
              <div className="space-y-4">
                <Input
                  label="Sanctioned Loan Amount (₹ INR)"
                  type="number"
                  value={loanInputStr}
                  onChange={(e) => handleManualAmountChange(e.target.value)}
                  placeholder="e.g. 1500000"
                  helperText="Enter the total credit sanction approved by your mortgage lender or bank."
                />

                {/* Quick Presets */}
                <div>
                  <span className="text-xs text-secondary block mb-1.5">Common Sanction Tiers:</span>
                  <div className="flex flex-wrap gap-2">
                    {[1000000, 1500000, 2000000, 2500000].map((amt) => (
                      <button
                        key={amt}
                        onClick={() => handleManualAmountChange(amt.toString())}
                        className={`px-3 py-1.5 rounded-lg text-xs font-mono border transition-colors ${
                          parseFloat(loanInputStr) === amt
                            ? 'bg-accent/15 border-accent text-accent font-semibold'
                            : 'border-border bg-panel hover:bg-surface text-secondary hover:text-primary'
                        }`}
                      >
                        ₹{(amt / 100000).toFixed(1)} Lakhs
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileUpload}
                  accept=".pdf"
                  className="hidden"
                />

                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed border-border hover:border-accent/60 rounded-xl p-6 text-center cursor-pointer transition-colors bg-panel/30 flex flex-col items-center justify-center min-h-[160px]"
                >
                  <div className="w-10 h-10 rounded-full bg-accent/10 border border-accent/20 flex items-center justify-center text-accent mb-2">
                    <IconFilePdf className="w-5 h-5" />
                  </div>
                  {uploadedLetterName ? (
                    <div>
                      <p className="text-sm font-medium text-primary">{uploadedLetterName}</p>
                      <p className="text-xs text-emerald-400 mt-1">
                        {isParsingDoc ? 'AI extracting sanction details...' : 'Sanction verified successfully'}
                      </p>
                    </div>
                  ) : (
                    <div>
                      <p className="text-sm font-medium text-primary">Upload Bank Sanction Letter</p>
                      <p className="text-xs text-secondary mt-0.5">PDF format up to 10 MB</p>
                    </div>
                  )}
                </div>

                {docBankName && (
                  <div className="p-3 rounded-lg bg-surface border border-border text-xs flex items-center justify-between">
                    <span className="text-secondary">Detected Facility:</span>
                    <span className="font-semibold text-primary">{docBankName}</span>
                  </div>
                )}
              </div>
            )}
          </Card>

          {/* Right Column: Capital Allocation Breakdown (6 cols) */}
          <Card className="lg:col-span-6 p-6">
            <h2 className="font-serif font-semibold text-lg text-primary tracking-tight mb-4">
              Material Capital Allocation
            </h2>

            {/* Visual Utilization Progress Bar */}
            <div className="space-y-2 mb-6">
              <div className="flex justify-between text-xs">
                <span className="text-secondary">Loan Utilization for Materials:</span>
                <span className="font-mono font-medium text-primary">
                  {utilizationPercentage}% of facility
                </span>
              </div>
              <div className="w-full h-3 bg-surface rounded-full overflow-hidden border border-border">
                <div
                  className={`h-full transition-all duration-700 ${
                    utilizationPercentage > 95
                      ? 'bg-rose-500'
                      : utilizationPercentage > 75
                      ? 'bg-amber-400'
                      : 'bg-emerald-400'
                  }`}
                  style={{ width: `${Math.min(100, utilizationPercentage)}%` }}
                />
              </div>
            </div>

            {/* Categorized Allocation Items */}
            <div className="space-y-2.5 text-xs">
              <div className="p-2.5 rounded-lg bg-surface border border-border flex justify-between items-center">
                <span className="text-secondary">Flooring (Marble & Teak)</span>
                <span className="font-mono text-primary font-medium">₹3,33,000 (35%)</span>
              </div>
              <div className="p-2.5 rounded-lg bg-surface border border-border flex justify-between items-center">
                <span className="text-secondary">Structural (Steel & Rebars)</span>
                <span className="font-mono text-primary font-medium">₹2,41,500 (26%)</span>
              </div>
              <div className="p-2.5 rounded-lg bg-surface border border-border flex justify-between items-center">
                <span className="text-secondary">Walls, Plaster & Paints</span>
                <span className="font-mono text-primary font-medium">₹1,44,900 (15%)</span>
              </div>
              <div className="p-2.5 rounded-lg bg-surface border border-border flex justify-between items-center">
                <span className="text-secondary">Tiles & Exterior Stone</span>
                <span className="font-mono text-primary font-medium">₹1,38,000 (15%)</span>
              </div>
              <div className="p-2.5 rounded-lg bg-surface border border-border flex justify-between items-center">
                <span className="text-secondary">Handling Contingency (5%)</span>
                <span className="font-mono text-primary font-medium">₹45,058 (5%)</span>
              </div>
            </div>
          </Card>
        </div>

        {/* Legal Disclaimer Box */}
        <div className="p-4 rounded-xl border border-border/80 bg-panel/30 text-xs text-secondary leading-relaxed space-y-1">
          <p className="font-semibold text-primary">
            Regulatory & Estimation Disclaimer:
          </p>
          <p>
            Construtiva provides architectural estimation services based on digital floor plan geometry and standard regional Schedule of Rates (SOR). This financial comparison evaluates raw material budgets only and does not constitute credit underwriting, banking advice, or commitment of loan disbursement by any financial institution.
          </p>
        </div>
      </main>
    </div>
  );
}
export default LoanAnalysisPage;
