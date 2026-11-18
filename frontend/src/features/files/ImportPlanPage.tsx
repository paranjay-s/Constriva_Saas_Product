import React, { useRef, useState, useEffect } from 'react';
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
import { useProject } from '../../context/ProjectContext';
import { filesApi, planFileProblem, type ParsingProgressEvent } from './api';
import { useUploadLimits } from './hooks/useUploadLimits';

type UploadStage = 'idle' | 'uploading' | 'parsing' | 'completed' | 'error';

interface PlanSummaryCounts {
  rooms: number;
  walls: number;
  openings: number;
}

/** What to tell the user next, by the parser's error code. */
const RETRY_HINTS: Record<string, string> = {
  llm_unavailable: 'The AI service was busy or unreachable. Nothing was saved; trying again in a moment usually works.',
  llm_rate_limited: 'The AI service is receiving too many requests. Nothing was saved; wait a minute, then try again.',
  llm_output_invalid: 'The drawing could not be read reliably. Nothing was saved. Try again, or use a clearer PDF of the floor plan.',
  no_floor_plan: 'No floor plan was found in this file. Nothing was saved. Choose a PDF that shows the floor plan with its rooms.',
  invalid_pdf: 'This file could not be opened as a PDF. Nothing was saved. Choose another file.',
  connection_lost: 'The connection dropped while the plan was being processed. Trying again is safe: a plan that was already read is not read twice.',
  not_signed_in: 'Sign in again, then upload the plan once more. A plan that was already read is not read twice.',
  job_not_found: 'This import is no longer available to follow. Upload the plan again; a plan that was already read is not read twice.',
};

export const ImportPlanPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [stage, setStage] = useState<UploadStage>('idle');
  const [currentProgress, setCurrentProgress] = useState(20);
  const [currentStepText, setCurrentStepText] = useState('Uploading blueprint...');
  // Counts of the plan that was just processed. Null until a real result is in.
  const [summary, setSummary] = useState<PlanSummaryCounts | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  // The parser's error code for a failed job (e.g. `llm_unavailable`), when there is one.
  const [errorCode, setErrorCode] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const sseCleanupRef = useRef<(() => void) | null>(null);
  const { activeProject, setProjectStatus, setPlanData } = useProject();
  const navigate = useNavigate();
  const limits = useUploadLimits();

  useEffect(() => {
    return () => {
      if (sseCleanupRef.current) {
        sseCleanupRef.current();
      }
    };
  }, []);

  const handleFileChange = (selectedFile: File) => {
    const problem = planFileProblem(selectedFile, limits);
    if (problem) {
      setErrorMessage(problem);
      return;
    }

    setErrorMessage(null);
    setErrorCode(null);
    setFile(selectedFile);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  // Every upload goes to the server. A plan is never taken from the browser by file name:
  // two different drawings can share a name. The server recognises a PDF it has already
  // parsed by its content, so a repeat upload is still fast.
  const handleProcessPlan = async () => {
    if (!file) return;

    if (sseCleanupRef.current) sseCleanupRef.current();
    setSummary(null);
    setStage('uploading');
    setErrorMessage(null);
    setErrorCode(null);
    setCurrentProgress(20);
    setCurrentStepText('Uploading PDF to secure storage...');

    try {
      const uploadRes = await filesApi.uploadBlueprint(file, activeProject?.id);
      setStage('parsing');
      setCurrentProgress(45);
      setCurrentStepText('Rendering 300 DPI raster and detecting geometric elements...');

      // Subscribe to real-time SSE progress stream
      const cleanup = filesApi.subscribeToProgress(uploadRes.task_id, {
        onProgress: (step: string, progress: number) => {
          setCurrentProgress(progress);
          setCurrentStepText(step);
        },
        onComplete: async (data: ParsingProgressEvent) => {
          // The job is done: load the plan it created, by its id. Only that plan is shown.
          const planId = data.result?.plan_id;
          try {
            if (!planId) throw new Error('The finished job did not name its plan.');
            const fetchedPlan = await filesApi.getPlanById(planId);
            if (!fetchedPlan?.plan_json) throw new Error('The processed plan came back empty.');
            setPlanData(fetchedPlan.plan_json);

            const counts = data.result?.plan_summary;
            const level = fetchedPlan.plan_json.levels?.[0];
            setSummary({
              rooms: counts?.rooms_count ?? level?.rooms?.length ?? 0,
              walls: counts?.walls_count ?? level?.walls?.length ?? 0,
              openings: counts?.openings_count ?? level?.openings?.length ?? 0,
            });
          } catch (err) {
            console.warn('Processed plan could not be loaded:', err);
            setStage('error');
            setErrorCode('plan_not_loaded');
            setErrorMessage('The plan was processed but could not be loaded. Please try again.');
            return;
          }

          setCurrentProgress(100);
          setStage('completed');
          setProjectStatus('imported');
        },
        onError: (errorMsg: string, code?: string) => {
          // The upload failed. Show why and offer a retry; no other plan is shown in its place.
          setStage('error');
          setErrorCode(code ?? null);
          setErrorMessage(errorMsg || 'The plan could not be processed.');
        },
      });

      sseCleanupRef.current = cleanup;
    } catch (err: any) {
      setStage('error');
      setErrorCode(null);
      setErrorMessage(err?.message || 'The upload could not be started.');
    }
  };

  const handleChooseAnotherFile = () => {
    if (sseCleanupRef.current) sseCleanupRef.current();
    setFile(null);
    setErrorMessage(null);
    setErrorCode(null);
    setSummary(null);
    setStage('idle');
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  return (
    <div className="flex-1 bg-[#101010] flex flex-col text-[#FFFFFF]">

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
          {errorMessage && stage !== 'error' && (
            <div role="alert" className="mb-6 p-4 rounded bg-[#351010] border border-[#FFB4AB]/40 text-[#FFB4AB] text-xs flex items-center gap-3">
              <AlertCircleIcon size={18} />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Failed: say why and offer a retry. No plan is shown in place of the one that failed. */}
          {stage === 'error' && (
            <div role="alert" className="py-6 flex flex-col items-center text-center">
              <div className="w-14 h-14 rounded-full bg-[#351010] border border-[#FFB4AB]/50 flex items-center justify-center text-[#FFB4AB] mb-4">
                <AlertCircleIcon size={24} />
              </div>
              <h3 className="font-display font-semibold text-2xl text-[#FFFFFF]">
                The plan could not be processed
              </h3>
              <p className="text-sm text-[#FFB4AB] mt-2 max-w-md">
                {errorMessage || 'The plan could not be processed.'}
              </p>
              <p className="text-xs text-[#A6A6A6] mt-2 max-w-md">
                {RETRY_HINTS[errorCode ?? ''] ?? 'Nothing was saved to this project. You can try again or choose another file.'}
              </p>
              {file && (
                <p className="text-[11px] font-mono text-[#737373] mt-3">
                  {file.name} • {formatFileSize(file.size)}
                </p>
              )}
              <div className="mt-6 flex flex-col sm:flex-row items-center gap-3 w-full max-w-md">
                <Button
                  variant="primary"
                  size="lg"
                  className="w-full"
                  disabled={!file}
                  onClick={() => handleProcessPlan()}
                >
                  Try again
                </Button>
                <Button variant="ghost" size="lg" className="w-full" onClick={handleChooseAnotherFile}>
                  Choose another file
                </Button>
              </div>
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
                    <span>Max Size: {limits.max_pdf_mb} MB</span>
                    <span>•</span>
                    <span>Up to {limits.max_pdf_pages} pages</span>
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
                  onClick={() => handleProcessPlan()}
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
                  {currentProgress}%
                </span>
              </div>

              <h3 className="font-display font-semibold text-xl text-[#FFFFFF]">
                Processing Architectural Blueprint
              </h3>
              <p className="text-sm text-[#A6A6A6] mt-2 max-w-md">
                {currentStepText}
              </p>

              {/* Progress Bar */}
              <div className="w-full max-w-md bg-[#101010] h-2 rounded-full overflow-hidden mt-6 border border-[#303030]">
                <div
                  className="bg-[#C5A77B] h-full transition-all duration-500 ease-out"
                  style={{ width: `${currentProgress}%` }}
                />
              </div>

              <p className="text-[11px] font-mono text-[#737373] uppercase tracking-widest mt-4">
                SSE Live Stream Active // Geometric Extractor
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
                Wall centerlines, interior room partitions, and openings compiled into Plan JSON.
              </p>

              {/* Extraction Summary Badges */}
              <div className="grid grid-cols-3 gap-3 w-full max-w-md my-6">
                <div className="p-3 rounded bg-[#141414] border border-[#303030] text-center">
                  <span className="block text-lg font-bold text-[#C5A77B] font-mono">{summary?.rooms ?? '–'}</span>
                  <span className="text-[10px] uppercase font-mono tracking-wider text-[#A6A6A6]">Rooms</span>
                </div>
                <div className="p-3 rounded bg-[#141414] border border-[#303030] text-center">
                  <span className="block text-lg font-bold text-[#C5A77B] font-mono">{summary?.walls ?? '–'}</span>
                  <span className="text-[10px] uppercase font-mono tracking-wider text-[#A6A6A6]">Walls</span>
                </div>
                <div className="p-3 rounded bg-[#141414] border border-[#303030] text-center">
                  <span className="block text-lg font-bold text-[#C5A77B] font-mono">{summary?.openings ?? '–'}</span>
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
                Open 3D Workspace
              </Button>

              <button
                type="button"
                onClick={handleChooseAnotherFile}
                className="text-xs text-[#A6A6A6] hover:text-[#C5A77B] underline mt-3 transition-colors"
              >
                Import a different plan
              </button>
            </div>
          )}
        </Card>
      </main>
    </div>
  );
};

