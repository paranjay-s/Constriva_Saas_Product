/**
 * BOQ raw material: upload a floor-plan PDF -> Uploading / Parsing / Calculating -> the
 * bill of quantities as a searchable table, with PDF and Excel downloads of the full list.
 * The assumptions behind the bill can be changed; that recalculates it from the plan
 * already read, and the downloads are always of the bill on screen.
 *
 * Quantities only (no money). Nothing is assumed about the rows: the table is built from
 * whatever items, categories and sub-categories the server returns.
 */
import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { AlertCircleIcon, ArrowLeftIcon, IconDownload, IconFilePdf, IconUpload } from '../../components/ui/Icons';
import { planFileProblem, useUploadLimits } from '../files';
import type { BoqAssumptionsInput, BoqResult } from './boqSchemas';
import { BoqAssumptions } from './components/BoqAssumptions';
import { BoqProgress } from './components/BoqProgress';
import { BoqSummary } from './components/BoqSummary';
import { BoqTable } from './components/BoqTable';
import { BoqUpload } from './components/BoqUpload';
import { BoqWarnings } from './components/BoqWarnings';
import { boqApi } from './boqApi';
import { useBoqExport } from './hooks/useBoqExport';
import { useBoqJob } from './hooks/useBoqJob';

function ErrorBanner({ message }: { message: string }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-xl border border-[#FFB4AB]/40 bg-[#351010] p-4 text-xs text-[#FFB4AB]">
      <AlertCircleIcon size={18} className="shrink-0" aria-hidden="true" />
      <span className="min-w-0 break-words leading-relaxed">{message}</span>
    </div>
  );
}

interface BoqResultViewProps {
  result: BoqResult;
  /** Name of the uploaded file, used when the result does not carry one. */
  sourceName: string | null;
  /** The person's own assumptions behind `result`; empty when they changed none. */
  choices: BoqAssumptionsInput;
  recalculating: boolean;
  recalculateError: string | null;
  onRecalculate: (choices: BoqAssumptionsInput) => void;
  onReset: () => void;
}

function BoqResultView(props: BoqResultViewProps) {
  const { result, sourceName, choices, recalculating, recalculateError, onRecalculate, onReset } = props;
  const exporter = useBoqExport(result, sourceName);
  // nothing to download from an empty bill; one download at a time; and not the bill that
  // a recalculation is about to replace
  const cannotExport = exporter.busy !== null || result.items.length === 0 || recalculating;
  const meta = result.project_metadata;
  const fileName = meta.source_file_name || sourceName;
  const title = meta.project_title || fileName || 'Bill of quantities';
  const facts = [meta.client, meta.building_type, meta.subject, title === fileName ? null : fileName].filter(
    (fact): fact is string => Boolean(fact),
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex min-w-0 flex-col gap-1">
          <span className="font-mono text-xs uppercase tracking-widest text-[#7ce8f2]">Bill of quantities</span>
          <h2 className="break-words text-2xl font-light tracking-[-0.02em] text-white">{title}</h2>
          {facts.length > 0 && <div className="break-words font-mono text-xs text-[#8b97a8]">{facts.join(' • ')}</div>}
        </div>
        <div className="flex flex-col gap-2 lg:items-end">
          <div className="flex flex-wrap gap-2">
            <Button
              variant="accent"
              size="sm"
              onClick={() => void exporter.download('pdf')}
              isLoading={exporter.busy === 'pdf'}
              disabled={cannotExport}
              aria-busy={exporter.busy === 'pdf'}
              leftIcon={<IconFilePdf className="h-3.5 w-3.5" aria-hidden="true" />}
            >
              Download PDF
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void exporter.download('xlsx')}
              isLoading={exporter.busy === 'xlsx'}
              disabled={cannotExport}
              aria-busy={exporter.busy === 'xlsx'}
              leftIcon={<IconDownload className="h-3.5 w-3.5" aria-hidden="true" />}
            >
              Download Excel
            </Button>
            <Button variant="ghost" size="sm" onClick={onReset} leftIcon={<IconUpload className="h-3.5 w-3.5" aria-hidden="true" />}>
              Upload another plan
            </Button>
          </div>
          {exporter.error && (
            <div role="alert" className="text-xs text-[#FFB4AB]">
              {exporter.error}
            </div>
          )}
        </div>
      </div>

      <BoqSummary summary={result.geometry_summary} itemCount={result.items.length} />
      {result.assumptions && (
        <BoqAssumptions
          assumptions={result.assumptions}
          choices={choices}
          busy={recalculating}
          error={recalculateError}
          onRecalculate={onRecalculate}
        />
      )}
      <BoqWarnings warnings={result.warnings} />
      <BoqTable items={result.items} />
    </div>
  );
}

export function BoqPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const job = useBoqJob();
  const { phase } = job;
  // a saved bill opened from the dashboard (?bill=<id>): shown as it was made
  const [params, setParams] = useSearchParams();
  const billId = params.get('bill');
  const [saved, setSaved] = useState<{ name: string; result: BoqResult } | null>(null);
  const [savedRecalcNote, setSavedRecalcNote] = useState<string | null>(null);
  const [savedError, setSavedError] = useState<string | null>(null);
  useEffect(() => {
    if (!billId) {
      setSaved(null);
      return;
    }
    let live = true;
    setSavedError(null);
    boqApi
      .savedBill(billId)
      .then(({ saved: s, result }) => live && setSaved({ name: s.name, result }))
      .catch((e: unknown) => live && setSavedError(e instanceof Error && e.message ? e.message : 'The saved bill could not be opened.'));
    return () => {
      live = false;
    };
  }, [billId]);
  const limits = useUploadLimits();

  const pick = (picked: File) => {
    const problem = planFileProblem(picked, limits);
    setFileError(problem);
    if (!problem) setFile(picked);
  };

  /** Back to the empty page (also stops following a run that is still going). */
  const reset = () => {
    if (billId) setParams({});
    job.reset();
    setFile(null);
    setFileError(null);
  };

  const working = phase === 'uploading' || phase === 'processing' || phase === 'loading_result';

  return (
    <div className="relative z-[2] flex flex-1 flex-col text-[#eef3f8]">
      <main className={`mx-auto w-full flex-1 px-4 py-6 sm:px-7 sm:py-8 ${phase === 'ready' ? 'max-w-7xl' : 'max-w-3xl'}`}>
        <div className="flex flex-col gap-8">
          <div className="flex flex-col items-start gap-6">
            <button
              type="button"
              onClick={() => navigate('/home')}
              className="inline-flex h-11 cursor-pointer items-center gap-2 rounded-full border border-white/10 bg-[rgba(10,14,21,0.78)] px-4 text-sm text-[#c9d3df] hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-[#bff6fb]"
            >
              <ArrowLeftIcon size={16} aria-hidden="true" />
              Back to Home
            </button>
            <div className="flex flex-col gap-1.5">
              <span className="font-mono text-xs uppercase tracking-[0.08em] text-[#bff6fb]">Pillar 03 // Quantities</span>
              <h1 className="text-[clamp(32px,3.6vw,48px)] font-light leading-[1.04] tracking-[-0.03em] text-white">BOQ Raw Material Sheet</h1>
              <div className="mt-2 text-[15px] leading-relaxed text-[#c9d3df]">
                Upload a floor plan PDF to get an itemised bill of quantities you can search, filter and download.
              </div>
            </div>
          </div>

          {savedError && <ErrorBanner message={savedError} />}
          {saved && phase !== 'ready' ? (
            <BoqResultView
              result={saved.result}
              sourceName={saved.name}
              choices={{}}
              recalculating={false}
              recalculateError={savedRecalcNote}
              onRecalculate={() => setSavedRecalcNote('Upload the PDF again to change the assumptions of a saved bill.')}
              onReset={reset}
            />
          ) : phase === 'ready' && job.result ? (
            <BoqResultView
              result={job.result}
              sourceName={file?.name ?? null}
              choices={job.assumptionsInput}
              recalculating={job.recalculating}
              recalculateError={job.recalculateError}
              onRecalculate={(choices) => void job.recalculate(choices)}
              onReset={reset}
            />
          ) : (
            <Card className="sm:p-8">
              {phase === 'idle' && (
                <div className="flex flex-col gap-6">
                  {fileError && <ErrorBanner message={fileError} />}
                  <BoqUpload
                    file={file}
                    limits={limits}
                    onPick={pick}
                    onClear={() => {
                      setFile(null);
                      setFileError(null);
                    }}
                    onStart={() => {
                      if (file) void job.start(file);
                    }}
                    onCancel={() => navigate('/home')}
                  />
                </div>
              )}

              {working && (
                <div className="flex flex-col gap-6">
                  <BoqProgress
                    uploading={phase === 'uploading'}
                    events={job.events}
                    fileName={file?.name}
                    loadingResult={phase === 'loading_result'}
                  />
                  <div className="flex justify-center border-t border-[#243041] pt-4">
                    <Button variant="ghost" size="sm" onClick={reset}>
                      Cancel
                    </Button>
                  </div>
                </div>
              )}

              {phase === 'error' && (
                <div className="flex flex-col gap-6">
                  <div className="flex flex-col gap-1.5">
                    <h2 className="text-[19px] font-medium text-white">The bill could not be prepared</h2>
                    {file && <div className="truncate font-mono text-xs text-[#8b97a8]">{file.name}</div>}
                  </div>
                  <ErrorBanner message={job.error ?? 'Something went wrong.'} />
                  <div className="flex flex-wrap items-center justify-end gap-2 border-t border-[#243041] pt-4">
                    {job.canRetryResult && (
                      <Button variant="secondary" onClick={job.retryResult}>
                        Retry
                      </Button>
                    )}
                    <Button variant="primary" onClick={reset}>
                      Try another file
                    </Button>
                  </div>
                </div>
              )}
            </Card>
          )}
        </div>
      </main>
    </div>
  );
}
