import React, { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import {
  AlertCircleIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
  CheckIcon,
  FilePdfIcon,
  TrashIcon,
  UploadIcon,
} from '../../components/ui/Icons';
import { Navbar } from '../../components/ui/Navbar';
import { useProject } from '../../context/ProjectContext';

type UploadStage = 'idle' | 'uploading' | 'parsing' | 'completed' | 'error';

interface ParsingStep {
  title: string;
  progress: number;
}

const PARSING_STEPS: ParsingStep[] = [
  { title: 'Uploading PDF to secure S3 object storage...', progress: 20 },
  { title: 'Rendering high-resolution architectural drawing...', progress: 45 },
  { title: 'Detecting structural wall centerlines and openings...', progress: 70 },
  { title: 'Calculating closed room polygons and floor areas...', progress: 90 },
  { title: 'Assembling Plan JSON and synchronizing material sheet...', progress: 100 },
];

export const ImportPlanPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [stage, setStage] = useState<UploadStage>('idle');
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const { activeProject, setProjectStatus } = useProject();
  const navigate = useNavigate();

  const handleFileChange = (selectedFile: File) => {
    if (!selectedFile.name.toLowerCase().endsWith('.pdf')) {
      setErrorMessage('Please upload an architectural document in PDF format.');
      return;
    }
    if (selectedFile.size > 50 * 1024 * 1024) {
      setErrorMessage('File size exceeds 50MB limit.');
      return;
    }

    setErrorMessage(null);
    setFile(selectedFile);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  const handleProcessPlan = async () => {
    if (!file) return;

    setStage('uploading');
    setErrorMessage(null);

    try {
      // Simulate presigned S3 upload & SSE worker task progress
      for (let i = 0; i < PARSING_STEPS.length; i++) {
        setCurrentStepIndex(i);
        if (i === 1) setStage('parsing');
        // Progressive architectural parsing simulation
        await new Promise((r) => setTimeout(r, 800));
      }

      setStage('completed');
      setProjectStatus('imported');
    } catch {
      setStage('error');
      setErrorMessage('Plan extraction failed. Please ensure the PDF is clear and uncorrupted.');
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  return (
    <div className="min-h-screen bg-[#101010] flex flex-col text-[#FFFFFF]">
      <Navbar />

      <main className="flex-1 max-w-3xl w-full mx-auto px-6 py-12">
        <button
          onClick={() => navigate('/projects/options')}
          disabled={stage === 'uploading' || stage === 'parsing'}
          className="inline-flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-[#A6A6A6] hover:text-[#FFFFFF] mb-8 cursor-pointer disabled:opacity-50"
        >
          <ArrowLeftIcon size={16} />
          Back to Options
        </button>

        <div className="mb-8">
          <span className="text-xs font-mono uppercase tracking-widest text-[#C5A77B]">
            Step 03 // Import 2D Plan
          </span>
          <h1 className="font-display font-semibold text-3xl tracking-tight text-[#FFFFFF] mt-1">
            Import Architectural Floor Plan
          </h1>
          <p className="text-sm text-[#A6A6A6] mt-2">
            Upload your building drawing in PDF format for project{' '}
            <span className="text-[#FFFFFF] font-semibold">{activeProject?.name || 'Current Project'}</span>.
          </p>
        </div>

        <Card className="bg-[#181818] border-[#303030] p-8">
          {errorMessage && (
            <div className="mb-6 p-4 rounded bg-[#351010] border border-[#FFB4AB]/40 text-[#FFB4AB] text-xs flex items-center gap-3">
              <AlertCircleIcon size={18} />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Idle: File Picker & Dropzone */}
          {stage === 'idle' && (
            <div className="flex flex-col gap-6">
              {!file ? (
                <div
                  onDragOver={(e) => {
                    e.preventDefault();
                    setIsDragging(true);
                  }}
                  onDragLeave={() => setIsDragging(false)}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`border-2 border-dashed rounded-lg p-10 flex flex-col items-center justify-center text-center cursor-pointer transition-all ${
                    isDragging
                      ? 'border-[#C5A77B] bg-[#202020]'
                      : 'border-[#303030] bg-[#141414] hover:border-[#444444] hover:bg-[#181818]'
                  }`}
                >
                  <input
                    type="file"
                    ref={fileInputRef}
                    accept="application/pdf"
                    className="hidden"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        handleFileChange(e.target.files[0]);
                      }
                    }}
                  />
                  <div className="w-14 h-14 rounded-full bg-[#202020] border border-[#303030] flex items-center justify-center text-[#C5A77B] mb-4">
                    <UploadIcon size={26} />
                  </div>
                  <h3 className="font-display font-semibold text-lg text-[#FFFFFF]">
                    Drag and drop your architectural PDF here
                  </h3>
                  <p className="text-xs text-[#A6A6A6] mt-1.5 max-w-sm">
                    Or click to browse your files. Single or multi-page architectural floor plans accepted.
                  </p>
                  <div className="mt-4 flex items-center gap-4 text-[11px] font-mono text-[#737373] uppercase tracking-wider">
                    <span>Format: PDF</span>
                    <span>•</span>
                    <span>Max Size: 50 MB</span>
                  </div>
                </div>
              ) : (
                <div className="p-5 rounded border border-[#303030] bg-[#141414] flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded bg-[#202020] border border-[#303030] flex items-center justify-center text-[#C5A77B]">
                      <FilePdfIcon size={20} />
                    </div>
                    <div>
                      <h4 className="text-sm font-semibold text-[#FFFFFF]">{file.name}</h4>
                      <p className="text-xs text-[#737373] font-mono">{formatFileSize(file.size)} • Ready to process</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => fileInputRef.current?.click()}
                    >
                      Replace
                    </Button>
                    <button
                      onClick={() => setFile(null)}
                      className="p-2 text-[#737373] hover:text-[#FFB4AB] transition-colors cursor-pointer"
                      title="Remove file"
                    >
                      <TrashIcon size={16} />
                    </button>
                    <input
                      type="file"
                      ref={fileInputRef}
                      accept="application/pdf"
                      className="hidden"
                      onChange={(e) => {
                        if (e.target.files && e.target.files[0]) {
                          handleFileChange(e.target.files[0]);
                        }
                      }}
                    />
                  </div>
                </div>
              )}

              <div className="flex items-center justify-between pt-4 border-t border-[#303030]">
                <Button
                  variant="ghost"
                  onClick={() => navigate('/projects/options')}
                >
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  size="lg"
                  disabled={!file}
                  onClick={handleProcessPlan}
                  rightIcon={<ArrowRightIcon size={16} />}
                >
                  Process Architectural Plan
                </Button>
              </div>
            </div>
          )}

          {/* Uploading & Parsing Stage */}
          {(stage === 'uploading' || stage === 'parsing') && (
            <div className="py-8 flex flex-col items-center text-center">
              <div className="w-16 h-16 rounded-full bg-[#141414] border border-[#C5A77B]/40 flex items-center justify-center mb-6 relative">
                <div className="absolute inset-0 rounded-full border-2 border-[#C5A77B] border-t-transparent animate-spin" />
                <span className="text-xs font-mono font-bold text-[#C5A77B]">
                  {PARSING_STEPS[currentStepIndex].progress}%
                </span>
              </div>

              <h3 className="font-display font-semibold text-xl text-[#FFFFFF]">
                Processing Floor Plan
              </h3>
              <p className="text-sm text-[#A6A6A6] mt-2 max-w-md">
                {PARSING_STEPS[currentStepIndex].title}
              </p>

              {/* Progress Bar */}
              <div className="w-full max-w-md bg-[#101010] h-2 rounded-full overflow-hidden mt-6 border border-[#303030]">
                <div
                  className="bg-[#C5A77B] h-full transition-all duration-500 ease-out"
                  style={{ width: `${PARSING_STEPS[currentStepIndex].progress}%` }}
                />
              </div>

              <p className="text-[11px] font-mono text-[#737373] uppercase tracking-widest mt-4">
                Celery Pipeline Active // Real-time Worker
              </p>
            </div>
          )}

          {/* Completed Stage */}
          {stage === 'completed' && (
            <div className="py-6 flex flex-col items-center text-center">
              <div className="w-14 h-14 rounded-full bg-[#102A1A] border border-[#10B981] flex items-center justify-center text-[#A7F3D0] mb-4">
                <CheckIcon size={24} />
              </div>
              <h3 className="font-display font-semibold text-2xl text-[#FFFFFF]">
                Plan Processed Successfully
              </h3>
              <p className="text-sm text-[#A6A6A6] mt-2 max-w-md">
                Wall centerlines, room boundaries, and openings have been compiled into Plan JSON.
              </p>

              {/* Extraction Summary Badges */}
              <div className="grid grid-cols-3 gap-3 w-full max-w-md my-6">
                <div className="p-3 rounded bg-[#141414] border border-[#303030] text-center">
                  <span className="block text-lg font-bold text-[#C5A77B] font-mono">5</span>
                  <span className="text-[10px] uppercase font-mono tracking-wider text-[#A6A6A6]">Rooms</span>
                </div>
                <div className="p-3 rounded bg-[#141414] border border-[#303030] text-center">
                  <span className="block text-lg font-bold text-[#C5A77B] font-mono">8</span>
                  <span className="text-[10px] uppercase font-mono tracking-wider text-[#A6A6A6]">Walls</span>
                </div>
                <div className="p-3 rounded bg-[#141414] border border-[#303030] text-center">
                  <span className="block text-lg font-bold text-[#C5A77B] font-mono">6</span>
                  <span className="text-[10px] uppercase font-mono tracking-wider text-[#A6A6A6]">Openings</span>
                </div>
              </div>

              <Button
                variant="primary"
                size="lg"
                onClick={() => navigate('/projects/3d-workspace')}
                rightIcon={<ArrowRightIcon size={16} />}
                className="w-full max-w-md"
              >
                Open 3D Workspace & Cost Sheet
              </Button>
            </div>
          )}
        </Card>
      </main>
    </div>
  );
};

