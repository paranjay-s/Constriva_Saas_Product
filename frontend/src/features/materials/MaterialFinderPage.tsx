/**
 * Material Finder: photo(s) + a prompt ("analyze this interior design", or "TV wall
 * 12 x 10 ft" for quantities straight away) -> identified materials, then follow-up chat
 * (sizes, a project, or an attached floor plan give quantities).
 *
 * Identification and quantities only (no money). The analysis id is kept in the URL
 * (?analysis=...), so a reload reopens the same session.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '../../components/ui/Button';
import { IconArrowLeft, IconSparkles } from '../../components/ui/Icons';
import { ApiError } from '../../lib/api';
import { useJobEvents } from '../floorplan';
import { MATERIAL_BASE, materialApi } from './api';
import { AnalysisProgress } from './components/AnalysisProgress';
import { AssumptionsPanel } from './components/AssumptionsPanel';
import { MaterialChat } from './components/MaterialChat';
import { ResultView } from './components/ResultView';
import { UploadPanel } from './components/UploadPanel';
import type { ManualSpace, Overrides, Session } from './schemas';

const JOB_SOURCE = { base: MATERIAL_BASE };

function errorText(e: unknown): string {
  if (e instanceof ApiError) return e.detail;
  if (e instanceof Error) return e.message;
  return 'Something went wrong.';
}

export function MaterialFinderPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();

  const [images, setImages] = useState<File[]>([]);
  const [prompt, setPrompt] = useState('');
  const [session, setSession] = useState<Session | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobKind, setJobKind] = useState<'analysis' | 'chat'>('analysis');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const assumptionsRef = useRef<HTMLDivElement>(null);

  const analysisId = params.get('analysis');
  const { events, latest, finished } = useJobEvents(jobId, JOB_SOURCE);
  const preview = useMemo(() => (images[0] ? URL.createObjectURL(images[0]) : null), [images]);
  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview);
  }, [preview]);

  const load = useCallback(async (id: string) => {
    try {
      setSession(await materialApi.get(id));
    } catch (e) {
      setError(errorText(e));
    }
  }, []);

  // reopen the session in the URL (reload, shared link)
  useEffect(() => {
    if (!analysisId || jobId || session?.id === analysisId) return;
    const req = { cancelled: false };
    materialApi
      .get(analysisId)
      .then((s) => {
        if (!req.cancelled) setSession(s);
      })
      .catch((e: unknown) => {
        if (!req.cancelled) setError(errorText(e));
      });
    return () => {
      req.cancelled = true;
    };
  }, [analysisId, jobId, session?.id]);

  // a finished job (analysis, plan reading, new focus): fetch the result once
  const handled = useRef<string | null>(null);
  useEffect(() => {
    if (!finished || !jobId || !analysisId || handled.current === jobId) return;
    handled.current = jobId;
    if (jobKind === 'analysis' && latest?.status === 'failed') return; // keep the reason on screen
    materialApi
      .get(analysisId)
      .then((s) => {
        setSession(s);
        setJobId(null);
      })
      .catch((e: unknown) => setError(errorText(e)));
  }, [finished, jobId, analysisId, latest?.status, jobKind]);

  const start = async () => {
    setError(null);
    if (images.length === 0) return setError('Add at least one photo.');
    setBusy(true);
    try {
      const res = await materialApi.start({
        images,
        focusAreas: [],
        focus: prompt.trim() || 'Analyze this interior design',
      });
      setSession(null);
      setJobKind('analysis');
      setJobId(res.job_id);
      setParams({ analysis: res.report_id });
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const recalc = async (manual: ManualSpace | null, overrides: Overrides) => {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      setSession(await materialApi.recalculate(session.id, manual, overrides));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const sendChat = async (message: string, file?: File | null) => {
    if (!session) return;
    setBusy(true);
    setError(null);
    // show the question at once
    setSession({ ...session, messages: [...session.messages, { role: 'user', text: message || `(attached ${file?.name})`, options: [] }] });
    try {
      const reply = await materialApi.chat(session.id, message, file);
      setSession(reply.session);
      if (reply.job_id) {
        setJobKind('chat');
        setJobId(reply.job_id);
      }
    } catch (e) {
      setError(errorText(e));
      void load(session.id);
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setSession(null);
    setJobId(null);
    setImages([]);
    setParams({});
  };

  /** After a failed analysis: back to the form with the same photos and settings. */
  const retry = () => {
    setSession(null);
    setJobId(null);
    setParams({});
  };

  const analysing = jobId !== null && jobKind === 'analysis' && !session;
  const working = jobId !== null && jobKind === 'chat' && !finished;
  const usingLabel = session?.report?.target?.label ?? (session?.project_name ? `project ${session.project_name}` : null);

  return (
    <div className="flex min-h-screen flex-col bg-[#0d0f12] font-sans text-white">
      <div role="toolbar" aria-label="Material finder" className="sticky top-0 z-30 flex items-center justify-between gap-4 border-b border-white/10 bg-[#0d0f12]/85 px-4 py-2.5 backdrop-blur-md sm:px-6">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate('/home')} leftIcon={<IconArrowLeft className="h-4 w-4" />} className="text-white/70 hover:text-white">
            Home
          </Button>
          <div className="hidden h-4 w-px bg-white/10 sm:block" />
          <div>
            <h1 className="flex items-center gap-2 text-sm font-medium sm:text-base">
              Material Finder
              <span className="flex items-center gap-1 rounded border border-[#C5A77B]/30 bg-[#C5A77B]/15 px-2 py-0.5 font-mono text-[10px] text-[#C5A77B]">
                <IconSparkles className="h-3 w-3" /> Vision AI
              </span>
            </h1>
            <p className="hidden font-mono text-[11px] text-white/50 sm:block">Identify finishes in a photo and get quantities for your own room.</p>
          </div>
        </div>
        {(session || jobId) && (
          <Button variant="secondary" size="sm" onClick={reset} className="border-white/10 bg-white/[0.04] text-xs">
            New analysis
          </Button>
        )}
      </div>

      <main className="mx-auto grid w-full max-w-7xl flex-1 grid-cols-1 gap-8 p-4 sm:p-6 lg:grid-cols-12 lg:p-8">
        {!session && !analysing && !analysisId && (
          <>
            <div className="space-y-5 lg:col-span-5">
              <UploadPanel images={images} onChange={setImages} />
            </div>
            <div className="space-y-6 lg:col-span-7">
              <label className="block space-y-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-[#9AA3B2]">Your prompt</span>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey && images.length > 0 && !busy) {
                      e.preventDefault();
                      void start();
                    }
                  }}
                  rows={3}
                  maxLength={500}
                  aria-label="Prompt"
                  placeholder="Analyze this interior design"
                  className="w-full resize-none rounded-lg border border-[#3A404B] bg-transparent px-3 py-2 text-sm text-white placeholder:text-[#5C6370] focus:border-[#C5A77B] focus:outline-none"
                />
                <span className="block text-[11px] text-[#5C6370]">
                  Add a size for quantities, e.g. "TV wall 12 x 10 ft" or "kitchen 10 x 8 ft". You can also ask in the chat afterwards.
                </span>
              </label>
              {error && <p role="alert" className="text-sm text-[#F2A0A2]">{error}</p>}
              <Button onClick={start} disabled={busy || images.length === 0} isLoading={busy}>
                Identify materials
              </Button>
            </div>
          </>
        )}

        {analysing && (
          <div className="mx-auto w-full max-w-md lg:col-span-12">
            <AnalysisProgress events={events} onRetry={retry} />
          </div>
        )}

        {session && (
          <>
            <div className="space-y-5 lg:col-span-5">
              {preview && <img src={preview} alt="Analysed photo" className="max-h-80 w-full rounded-xl border border-white/10 object-cover" />}
              {session.focus && <p className="text-xs text-[#9AA3B2]">Prompt: {session.focus}</p>}
              {session.report && (
                <div ref={assumptionsRef}>
                  <AssumptionsPanel
                    key={`${session.report.target?.label ?? ''}-${session.report.version}`}
                    report={session.report}
                    materials={session.materials}
                    busy={busy}
                    onApply={recalc}
                  />
                </div>
              )}
            </div>
            <div className="space-y-6 lg:col-span-7">
              <ResultView materials={session.materials} report={session.report} focusNote={session.focus_found ? '' : session.focus_note} />
              {error && <p role="alert" className="text-sm text-[#F2A0A2]">{error}</p>}
              <MaterialChat
                messages={session.messages}
                pendingOptions={session.pending_question?.options ?? []}
                usingLabel={usingLabel}
                busy={busy || working}
                thinking={working ? latest?.detail || 'Working…' : busy ? 'Thinking…' : null}
                onSend={sendChat}
                onEditSpace={() => assumptionsRef.current?.scrollIntoView?.({ behavior: 'smooth' })}
              />
            </div>
          </>
        )}

        {!session && !analysing && analysisId && (
          <div className="lg:col-span-12">
            {error ? (
              <div className="space-y-3">
                <p role="alert" className="text-sm text-[#F2A0A2]">{error}</p>
                <Button variant="secondary" size="sm" onClick={reset}>
                  Start a new analysis
                </Button>
              </div>
            ) : (
              <p className="text-sm text-[#9AA3B2]">Loading…</p>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
