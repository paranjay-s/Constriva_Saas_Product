/**
 * Material Finder as a chat: attach photo(s) and ask ("analyze this interior", or "TV wall
 * 12 x 10 ft" for quantities straight away). The materials and quantities open in the side
 * panel; follow-ups (sizes, a project, an attached floor plan, alternatives) continue in
 * the same conversation.
 *
 * Identification and quantities only (no money). The analysis id is kept in the URL
 * (?analysis=...), so a reload, a shared link or the sidebar history reopens it.
 */
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import { ApiError } from '../../lib/api';
import { useJobEvents } from '../floorplan';
import { Chips, Composer } from '../studio/Composer';
import { Headline } from '../studio/Headline';
import { Icon } from '../studio/icons';
import { Dock, type PanelSpec, Stage, Status, StudioShell, useStudio } from '../studio/StudioShell';
import { type Signals, StudioSync } from '../studio/StudioSync';
import { AiMessage, ArtifactCard, QuickReplies, Thread, Typing, UserMessage } from '../studio/Thread';
import { MATERIAL_BASE, materialApi } from './api';
import { AssumptionsPanel } from './components/AssumptionsPanel';
import { ResultView } from './components/ResultView';
import type { ManualSpace, Overrides, Session } from './schemas';

const JOB_SOURCE = { base: MATERIAL_BASE };
const MAX_IMAGES = 4;
const PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const PLAN_ACCEPT = 'application/pdf,image/png,image/jpeg';
const LINES = [
  'find every *finish* in this room',
  'what is that *wall made of*?',
  'quantities for a *12 × 10 ft* wall',
  'what can I use *instead*?',
];
const STARTERS = [
  { cmd: 'analyze this interior', prompt: 'Analyze this interior design' },
  { cmd: 'TV wall 12×10 ft', prompt: 'TV wall 12 x 10 ft, give me the quantities' },
  { cmd: 'kitchen 10×8 ft', prompt: 'Kitchen 10 x 8 ft, what materials and how much?' },
  { cmd: 'floor only', prompt: 'Only the flooring, room is 14 x 12 ft' },
];
const FOLLOW_UPS = [
  'Replicate this design in my floor plan',
  'How did you calculate the quantities?',
  'What can I use instead of this?',
  'What else do I need along with these?',
];

function errorText(e: unknown): string {
  if (e instanceof ApiError) return e.detail;
  if (e instanceof Error) return e.message;
  return 'Something went wrong.';
}

export function MaterialFinderPage() {
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const analysisId = params.get('analysis');

  const [draft, setDraft] = useState('');
  const [images, setImages] = useState<File[]>([]);
  const [planFile, setPlanFile] = useState<File | null>(null);
  const [asked, setAsked] = useState<{ text: string; previews: string[] } | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobKind, setJobKind] = useState<'analysis' | 'chat'>('analysis');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [composerError, setComposerError] = useState(false);
  const [panelOpen, setPanelOpen] = useState(true);
  const [serverPhoto, setServerPhoto] = useState<string | null>(null);
  const [signals, setSignals] = useState<Signals>({ working: false, pulse: 0, dim: 0, facing: null, history: 0 });
  const photoInput = useRef<HTMLInputElement>(null);
  const planInput = useRef<HTMLInputElement>(null);
  const { events, latest, finished } = useJobEvents(jobId, JOB_SOURCE);

  const previews = useMemo(() => images.map((f) => URL.createObjectURL(f)), [images]);
  useEffect(() => () => previews.forEach((u) => URL.revokeObjectURL(u)), [previews]);

  // ------------------------------------------------------------- loading
  const load = useCallback(async (id: string) => {
    try {
      setSession(await materialApi.get(id));
    } catch (e) {
      setError(errorText(e));
    }
  }, []);

  useEffect(() => {
    if (!analysisId || jobId || session?.id === analysisId) return;
    const req = { cancelled: false };
    setAsked(null);
    materialApi
      .get(analysisId)
      .then((s) => {
        if (!req.cancelled) {
          setSession(s);
          setPanelOpen(true);
        }
      })
      .catch((e: unknown) => {
        if (!req.cancelled) setError(errorText(e));
      });
    return () => {
      req.cancelled = true;
    };
  }, [analysisId, jobId, session?.id]);

  // a new chat (sidebar "New image analysis", even from this page) clears everything
  const lastKey = useRef(location.key);
  useEffect(() => {
    if (lastKey.current === location.key) return;
    lastKey.current = location.key;
    if (params.get('analysis')) return;
    setSession(null);
    setJobId(null);
    setAsked(null);
    setImages([]);
    setPlanFile(null);
    setDraft('');
    setError(null);
    setSignals((s) => ({ ...s, working: false }));
  }, [location.key, params]);

  // a finished job (analysis, reading a plan): fetch the result once
  const handled = useRef<string | null>(null);
  useEffect(() => {
    if (!finished || !jobId || !analysisId || handled.current === jobId) return;
    handled.current = jobId;
    const failed = latest?.status === 'failed';
    setSignals((s) => ({ ...s, working: false, pulse: failed ? s.pulse : s.pulse + 1, dim: failed ? s.dim + 1 : s.dim, history: s.history + 1 }));
    if (jobKind === 'analysis' && failed) return; // keep the reason on screen
    materialApi
      .get(analysisId)
      .then((s) => {
        setSession(s);
        setJobId(null);
        setPanelOpen(true);
      })
      .catch((e: unknown) => setError(errorText(e)));
  }, [finished, jobId, analysisId, latest?.status, jobKind]);

  // the server's copy of the photo, for reopened analyses
  const sessionId = session?.id ?? null;
  const localPhoto = previews[0] ?? asked?.previews[0] ?? null;
  useEffect(() => {
    if (!sessionId || localPhoto) return;
    let url: string | null = null;
    let cancelled = false;
    materialApi
      .image(sessionId)
      .then((u) => {
        url = u;
        if (cancelled && u) URL.revokeObjectURL(u);
        else setServerPhoto(u);
      })
      .catch(() => setServerPhoto(null));
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
      setServerPhoto(null);
    };
  }, [sessionId, localPhoto]);
  const photo = localPhoto ?? serverPhoto;

  // ------------------------------------------------------------- actions
  const addPhotos = (list: FileList | null) => {
    if (!list) return;
    const picked = Array.from(list).filter((f) => PHOTO_TYPES.includes(f.type));
    setImages((cur) => [...cur, ...picked].slice(0, MAX_IMAGES));
    setComposerError(false);
  };

  const start = async () => {
    setError(null);
    if (images.length === 0) {
      setComposerError(true);
      setError('Add a photo first: the plus button, or drop it on the message box.');
      setSignals((s) => ({ ...s, dim: s.dim + 1 }));
      return;
    }
    setBusy(true);
    const text = draft.trim() || 'Analyze this interior design';
    try {
      const res = await materialApi.start({ images, focusAreas: [], focus: text });
      setAsked({ text, previews: images.map((f) => URL.createObjectURL(f)) });
      setSession(null);
      setJobKind('analysis');
      setJobId(res.job_id);
      setDraft('');
      setSignals((s) => ({ ...s, working: true }));
      setParams({ analysis: res.report_id });
    } catch (e) {
      setError(errorText(e));
      setSignals((s) => ({ ...s, dim: s.dim + 1 }));
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
      setSignals((s) => ({ ...s, pulse: s.pulse + 1 }));
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
    setSignals((s) => ({ ...s, working: true }));
    setSession({ ...session, messages: [...session.messages, { role: 'user', text: message || `(attached ${file?.name})`, options: [] }] });
    try {
      const reply = await materialApi.chat(session.id, message, file);
      setSession(reply.session);
      if (reply.job_id) {
        setJobKind('chat');
        setJobId(reply.job_id);
      } else {
        setSignals((s) => ({ ...s, working: false, pulse: s.pulse + 1 }));
        if (reply.session.report) setPanelOpen(true);
      }
    } catch (e) {
      setError(errorText(e));
      setSignals((s) => ({ ...s, working: false, dim: s.dim + 1 }));
      void load(session.id);
    } finally {
      setBusy(false);
    }
  };

  const submit = (text = draft) => {
    if (busy) return;
    if (!session) {
      void start();
      return;
    }
    const msg = text.trim();
    if (!msg && !planFile) {
      setComposerError(true);
      setSignals((s) => ({ ...s, dim: s.dim + 1 }));
      return;
    }
    setComposerError(false);
    setDraft('');
    const f = planFile;
    setPlanFile(null);
    void sendChat(msg, f);
  };

  const retry = () => {
    setSession(null);
    setJobId(null);
    setAsked(null);
    setParams({});
  };

  // ------------------------------------------------------------- view
  const analysing = jobId !== null && jobKind === 'analysis' && !session;
  const working = jobId !== null && jobKind === 'chat' && !finished;
  const chatting = Boolean(session) || analysing || Boolean(analysisId) || Boolean(asked);
  const firstAi = session ? session.messages.findIndex((m) => m.role === 'assistant') : -1;
  const lastIsAi = session ? session.messages.length > 0 && session.messages[session.messages.length - 1].role === 'assistant' : false;
  const options = session?.pending_question?.options ?? [];
  const scene = session?.scene ? session.scene[0].toUpperCase() + session.scene.slice(1) : 'Materials';
  const withQty = session?.report?.lines?.length ?? 0;

  const panel: PanelSpec | null =
    session && panelOpen && (session.materials.length > 0 || session.report)
      ? {
          title: `${scene} · materials`,
          body: (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
              {photo && (
                <img
                  src={photo}
                  alt="Analysed photo"
                  style={{ width: '100%', maxHeight: 260, objectFit: 'cover', borderRadius: 14, border: '1px solid var(--border)' }}
                />
              )}
              <ResultView materials={session.materials} report={session.report} focusNote={session.focus_found ? '' : session.focus_note} />
              {session.report && (
                <AssumptionsPanel
                  key={`${session.report.target?.label ?? ''}-${session.report.version}`}
                  report={session.report}
                  materials={session.materials}
                  busy={busy}
                  onApply={recalc}
                />
              )}
            </div>
          ),
        }
      : null;

  const attachments =
    images.length > 0 || planFile ? (
      <div className="st-attachments">
        {!session &&
          images.map((f, i) => (
            <div key={`${f.name}-${i}`} className="st-thumb">
              <img src={previews[i]} alt={f.name} />
              <button type="button" aria-label={`Remove ${f.name}`} onClick={() => setImages((cur) => cur.filter((_, j) => j !== i))}>
                <Icon name="x" small />
              </button>
            </div>
          ))}
        {planFile && (
          <span className="st-file">
            <Icon name="clip" small />
            <span className="st-fname">{planFile.name}</span>
            <button type="button" aria-label={`Remove ${planFile.name}`} onClick={() => setPlanFile(null)}>
              <Icon name="x" small />
            </button>
          </span>
        )}
      </div>
    ) : null;

  const composer = (
    <div
      style={{ width: '100%' }}
      onDragOver={(e) => {
        if (!session) e.preventDefault();
      }}
      onDrop={(e) => {
        if (session) return;
        e.preventDefault();
        addPhotos(e.dataTransfer.files);
      }}
    >
      <input ref={photoInput} type="file" accept={PHOTO_TYPES.join(',')} multiple hidden onChange={(e) => addPhotos(e.target.files)} />
      <input
        ref={planInput}
        type="file"
        accept={PLAN_ACCEPT}
        hidden
        onChange={(e) => {
          setPlanFile(e.target.files?.[0] ?? null);
          e.target.value = '';
        }}
      />
      <Composer
        value={draft}
        onChange={(v) => {
          setDraft(v);
          if (composerError) setComposerError(false);
        }}
        onSubmit={() => submit()}
        label={session ? 'Ask a follow-up' : 'Ask about the photo'}
        placeholder={
          session
            ? 'Ask a follow-up: sizes, your project, “what can I use instead?”…'
            : images.length
              ? 'Analyze this interior… add a size for quantities, e.g. TV wall 12 × 10 ft'
              : 'Attach a photo of a room, then ask about it'
        }
        busy={busy || analysing || working}
        ready={!session && images.length > 0}
        error={composerError}
        attachments={attachments}
        onAttach={() => (session ? planInput.current?.click() : photoInput.current?.click())}
        attachLabel={session ? 'Attach a floor plan (PDF, PNG or JPG)' : 'Add photos (up to 4)'}
        hint={session ? '↵ send · ⇧↵ new line' : '↵ analyse · ⇧↵ new line'}
        autoFocus
      />
    </div>
  );

  return (
    <StudioShell
      theme="blueprint"
      agent="analysis"
      currentId={session?.id ?? analysisId}
      title={chatting ? (session?.scene ? scene : 'Image analysis') : undefined}
      meta={session?.report?.target?.label ?? (session?.project_name ? `project ${session.project_name}` : undefined)}
      chatting={chatting}
      topActions={
        panel === null && session && (session.materials.length > 0 || session.report) ? (
          <button type="button" className="st-pill" onClick={() => setPanelOpen(true)}>
            <Icon name="image" small /> Show results
          </button>
        ) : null
      }
      panel={panel}
      onClosePanel={() => setPanelOpen(false)}
    >
      <StudioSync {...signals} />
      {!chatting ? (
        <EmptyState composer={composer} onPick={setDraft} paused={draft.trim() !== ''} error={error} hasPhoto={images.length > 0} />
      ) : (
        <>
          <Thread stamp={`${session?.messages.length ?? 0}-${events.length}-${working}-${busy}-${error}`}>
            {asked && !session && <UserMessage text={asked.text} images={asked.previews} />}
            {analysing &&
              (latest?.status === 'failed' ? (
                <AiMessage tone="error" text={`I could not finish the analysis. ${latest.error ?? ''}`.trim()}>
                  <button type="button" className="st-btn" style={{ marginTop: 10 }} onClick={retry}>
                    <Icon name="undo" small />
                    Try again
                  </button>
                </AiMessage>
              ) : (
                <Typing label={latest?.detail || 'Looking at the photo'} />
              ))}
            {!session && !analysing && analysisId && !error && <Typing label="Opening the analysis" />}

            {session &&
              session.messages.map((m, i) =>
                m.role === 'user' ? (
                  <UserMessage key={i} text={m.text} images={i === 0 && photo ? [photo] : undefined} />
                ) : (
                  <AiMessage key={i} text={m.text} tone={m.status === 'failed' || m.status === 'not_found' ? 'error' : m.status === 'needs_input' ? 'warn' : undefined}>
                    {i === firstAi && (session.materials.length > 0 || session.report) && (
                      <ArtifactCard
                        title={`${scene}: ${session.materials.length} material${session.materials.length === 1 ? '' : 's'}`}
                        meta={withQty ? `${withQty} quantity line${withQty === 1 ? '' : 's'} · open to see how they were worked out` : 'Give a size to get quantities'}
                        thumb={photo}
                        icon="image"
                        open={panelOpen}
                        onOpen={() => setPanelOpen(true)}
                      />
                    )}
                  </AiMessage>
                ),
              )}
            {session && session.messages.length === 0 && (
              <AiMessage text={`I found **${session.materials.length}** material${session.materials.length === 1 ? '' : 's'}.`}>
                <ArtifactCard title={`${scene} · materials`} meta="Open the results" thumb={photo} icon="image" open={panelOpen} onOpen={() => setPanelOpen(true)} />
              </AiMessage>
            )}
            {session && lastIsAi && !working && (
              <QuickReplies options={options.length ? options : session.messages.length <= 2 ? FOLLOW_UPS : []} disabled={busy} onPick={(o) => submit(o)} />
            )}
            {working && <Typing label={latest?.detail || 'Working on it'} />}
            {busy && !working && session && <Typing label="Thinking" />}
            {error && <AiMessage text={error} tone="error" />}
          </Thread>
          <Dock>{composer}</Dock>
        </>
      )}
    </StudioShell>
  );
}

function EmptyState(p: { composer: ReactNode; onPick: (prompt: string) => void; paused: boolean; error: string | null; hasPhoto: boolean }) {
  const { motionOn, userName } = useStudio();
  return (
    <Stage footnote="Material Finder · the AI names the finishes, code calculates every quantity">
      <Headline name={userName} lines={LINES} playing={motionOn} paused={p.paused} />
      {p.composer}
      <Chips items={STARTERS} onPick={p.onPick} />
      {p.error ? (
        <Status tone="error">{p.error}</Status>
      ) : (
        !p.hasPhoto && <Status>Start by attaching a photo with the <strong>+</strong> button, or drop it on the message box.</Status>
      )}
    </Stage>
  );
}
