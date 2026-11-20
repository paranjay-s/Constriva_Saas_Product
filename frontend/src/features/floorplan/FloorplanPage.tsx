/**
 * AI floor plan generator as a chat:
 *
 *   describe the house -> "Is this right?" card -> live progress -> the plan opens in the
 *   side panel -> change it in the same conversation (sizes, facing, doors, undo...).
 *
 * The plan id is kept in the URL (?plan=...), so a reload, a shared link or the history
 * in the sidebar reopens the same chat. Every plan is saved inside one of the user's
 * projects, chosen in the composer.
 */
import { type ReactNode, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { useProject } from '../../context/ProjectContext';
import { ApiError } from '../../lib/api';
import { Chips, Composer } from '../studio/Composer';
import { Headline } from '../studio/Headline';
import { Icon } from '../studio/icons';
import { ProjectMenu, isSavedProject } from '../studio/ProjectMenu';
import { Dock, type PanelSpec, Stage, Status, StudioShell, useStudio } from '../studio/StudioShell';
import { type Signals, StudioSync } from '../studio/StudioSync';
import { AiMessage, ArtifactCard, QuickReplies, Thread, Typing, UserMessage } from '../studio/Thread';
import { plan3dApi, plan3dErrorText } from '../plan3d';
import { floorplanApi } from './api';
import { ConfirmationCard, type PlanNames } from './components/ConfirmationCard';
import { ExportMenu } from './components/ExportMenu';
import { PlanViewer2D } from './components/PlanViewer2D';
import { useJobEvents } from './hooks/useJobEvents';
import { type BriefFormValues, EMPTY_FORM, type ParseResponse, type PlanResponse } from './schemas';

const LINES = [
  'draw a 3 BHK on a *30 × 40 ft plot*',
  'plan a *north-facing* villa',
  'fit *four bedrooms* on a 40 × 60 ft plot',
  'design a home around a *courtyard*',
  'add a *pool* beside the house',
];
const STARTERS = [
  { cmd: '3 BHK on 30×40 ft', prompt: '3 BHK house on a 30 x 40 ft plot, road on the east, 2 bathrooms and car parking' },
  { cmd: 'north-facing villa', prompt: '4 bedroom north-facing villa on a 50 x 80 ft plot with a family hall and a swimming pool' },
  { cmd: 'compact 2 BHK', prompt: '2 BHK on a 25 x 40 ft plot, road on the south' },
  { cmd: 'courtyard home', prompt: '3 bedroom home with a central courtyard on a 40 x 60 ft plot' },
];
const EDIT_IDEAS = ['Make it east facing', 'Area statement', 'Make the master bedroom bigger', 'Which way do the rooms face?'];

type Turn =
  | { kind: 'user'; text: string }
  | { kind: 'brief'; parsed: ParseResponse }
  | { kind: 'note'; text: string; tone?: 'error' | 'warn' }
  | { kind: 'job'; jobId: string };

function errorText(e: unknown): string {
  if (e instanceof ApiError) return e.detail;
  if (e instanceof Error) return e.message;
  return 'Something went wrong.';
}

export function FloorplanPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const generatedId = useRef<string | null>(null); // the plan made in this chat
  const planId = params.get('plan');
  const { projects, activeProject, isLoadingProjects, projectsError, fetchProjects, selectProject } =
    useProject();
  const project = isSavedProject(activeProject, projects) ? activeProject : null;

  const [draft, setDraft] = useState('');
  const [briefText, setBriefText] = useState(''); // everything said about the house so far
  const [turns, setTurns] = useState<Turn[]>([]);
  const [parsed, setParsed] = useState<ParseResponse | null>(null);
  const [names, setNames] = useState<PlanNames>({ project: '', owner: '' }); // title block
  const [jobId, setJobId] = useState<string | null>(null);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [thinking, setThinking] = useState<string | null>(null);
  const [pendingUser, setPendingUser] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(true);
  const [menuOpen, setMenuOpen] = useState(false);
  const [needProject, setNeedProject] = useState(false);
  const [composerError, setComposerError] = useState(false);
  const [signals, setSignals] = useState<Signals>({ working: false, pulse: 0, dim: 0, facing: null, history: 0 });
  const bump = (k: 'pulse' | 'dim' | 'history') => setSignals((s) => ({ ...s, [k]: s[k] + 1 }));

  const progress = useJobEvents(jobId);
  const generating = jobId !== null && !(progress.finished && progress.latest?.status === 'failed');

  // ---------------------------------------------------------------- loading a plan
  const loadingPlan = Boolean(planId) && plan?.id !== planId;
  useEffect(() => {
    if (!planId || plan?.id === planId) return;
    if (planId !== generatedId.current) {
      // another chat from the history: start from its own messages
      setTurns([]);
      setParsed(null);
      setNames({ project: '', owner: '' });
      setBriefText('');
    }
    const req = { cancelled: false };
    floorplanApi
      .plan(planId)
      .then((p) => {
        if (req.cancelled) return;
        setPlan(p);
        setPanelOpen(true);
      })
      .catch((e: unknown) => {
        if (req.cancelled) return;
        setTurns((t) => [...t, { kind: 'note', text: errorText(e), tone: 'error' }]);
        setParams({}, { replace: true });
      });
    return () => {
      req.cancelled = true;
    };
  }, [planId, plan?.id, setParams]);

  // a new chat (sidebar "New floor plan", even from this page) clears everything
  const lastKey = useRef(location.key);
  useEffect(() => {
    if (lastKey.current === location.key) return;
    lastKey.current = location.key;
    if (params.get('plan')) return;
    generatedId.current = null;
    setPlan(null);
    setTurns([]);
    setParsed(null);
    setNames({ project: '', owner: '' });
    setBriefText('');
    setJobId(null);
    setDraft('');
    setSignals((s) => ({ ...s, working: false }));
  }, [location.key, params]);

  // the plan's project becomes the active one (so "Open in 3D" and the home page match)
  useEffect(() => {
    const pid = plan?.project_id;
    if (!pid || activeProject?.id === pid) return;
    const owner = projects.find((p) => p.id === pid);
    if (owner) void selectProject(owner);
  }, [plan?.project_id, activeProject?.id, projects, selectProject]);

  // the job finished: open the plan
  useEffect(() => {
    const ev = progress.latest;
    if (!jobId || !ev) return;
    if (ev.status === 'done' && ev.plan_id) {
      generatedId.current = ev.plan_id;
      setJobId(null);
      setSignals((s) => ({ ...s, working: false, pulse: s.pulse + 1, history: s.history + 1 }));
      setPanelOpen(true);
      setParams({ plan: ev.plan_id });
    } else if (ev.status === 'failed') {
      setSignals((s) => ({ ...s, working: false, dim: s.dim + 1 }));
    }
  }, [progress.latest, jobId, setParams]);

  useEffect(() => {
    setSignals((s) => (s.facing === (plan?.facing ?? null) ? s : { ...s, facing: plan?.facing ?? null }));
  }, [plan?.facing]);

  // ---------------------------------------------------------------- actions
  const parseBrief = async (text: string) => {
    setBusy(true);
    setThinking('Reading your brief');
    try {
      const values = { ...EMPTY_FORM, prompt: text.slice(0, 4000) } as BriefFormValues;
      const res = await floorplanApi.parseBrief(values);
      setParsed(res);
      // names said in the prompt fill the card; names typed into the card are kept
      setNames((n) => ({ project: res.brief.project_name || n.project, owner: res.brief.owner_name || n.owner }));
      setTurns((t) => [...t, { kind: 'brief', parsed: res }]);
      if (res.ready && !project) setNeedProject(true);
    } catch (e) {
      setTurns((t) => [...t, { kind: 'note', text: errorText(e), tone: 'error' }]);
      bump('dim');
    } finally {
      setBusy(false);
      setThinking(null);
    }
  };

  const generate = async () => {
    if (!parsed) return;
    if (!project) {
      setNeedProject(true);
      setMenuOpen(true);
      setTurns((t) => [...t, { kind: 'note', text: 'Choose the project to save this plan in (the **Choose project** button below the message box), then press Generate again.', tone: 'warn' }]);
      return;
    }
    setBusy(true);
    try {
      const brief = {
        ...parsed.brief,
        project_name: (names.project.trim() || project.name).slice(0, 120),
        owner_name: names.owner.trim().slice(0, 120),
      };
      const id = await floorplanApi.generate(brief, project.id);
      setJobId(id);
      setTurns((t) => [...t, { kind: 'job', jobId: id }]);
      setSignals((s) => ({ ...s, working: true }));
    } catch (e) {
      setTurns((t) => [...t, { kind: 'note', text: errorText(e), tone: 'error' }]);
      bump('dim');
    } finally {
      setBusy(false);
    }
  };

  const sendEdit = async (text: string) => {
    if (!plan) return;
    setBusy(true);
    setPendingUser(text);
    setThinking('Changing the plan');
    setSignals((s) => ({ ...s, working: true }));
    try {
      const res = await floorplanApi.edit(plan.id, text, plan.version);
      setPlan(res.plan);
      setSignals((s) => ({
        ...s,
        working: false,
        pulse: res.status === 'ok' || res.status === 'info' ? s.pulse + 1 : s.pulse,
        dim: res.status === 'impossible' || res.status === 'failed' ? s.dim + 1 : s.dim,
        history: res.status === 'ok' ? s.history + 1 : s.history,
      }));
      if (res.status === 'ok') setPanelOpen(true);
    } catch (e) {
      setSignals((s) => ({ ...s, working: false, dim: s.dim + 1 }));
      if (e instanceof ApiError && e.status === 409) {
        setTurns((t) => [...t, { kind: 'note', text: 'The plan was changed somewhere else; the latest version is loaded. Please send again.', tone: 'warn' }]);
        setPlan(await floorplanApi.plan(plan.id).catch(() => plan));
      } else {
        setTurns((t) => [...t, { kind: 'note', text: errorText(e), tone: 'error' }]);
      }
    } finally {
      setPendingUser(null);
      setThinking(null);
      setBusy(false);
    }
  };

  const submit = (text = draft) => {
    const msg = text.trim();
    if (!msg) {
      setComposerError(true);
      bump('dim');
      return;
    }
    if (busy || generating) return;
    setComposerError(false);
    setDraft('');
    if (plan) {
      void sendEdit(msg);
      return;
    }
    setTurns((t) => [...t, { kind: 'user', text: msg }]);
    const full = briefText ? `${briefText}\n${msg}` : msg;
    setBriefText(full);
    void parseBrief(full);
  };

  const revert = async (version?: number) => {
    if (!plan) return;
    setBusy(true);
    try {
      const res = await floorplanApi.revert(plan.id, version);
      setPlan(res.plan);
      if (res.status === 'ok') bump('pulse');
    } catch (e) {
      setTurns((t) => [...t, { kind: 'note', text: errorText(e), tone: 'error' }]);
    } finally {
      setBusy(false);
    }
  };

  // "Open in 3D" hands the stored plan to the 3D builder (no drawing is read) and opens its job
  const [opening3d, setOpening3d] = useState(false);
  const openIn3D = async () => {
    if (!plan || opening3d) return;
    setOpening3d(true);
    try {
      const { job_id } = await plan3dApi.fromFloorplan(plan.id);
      navigate(`/3d/${encodeURIComponent(job_id)}`);
    } catch (e) {
      setTurns((t) => [...t, { kind: 'note', text: `The plan could not be opened in 3D. ${plan3dErrorText(e)}`, tone: 'error' }]);
      setOpening3d(false);
    }
  };

  // ---------------------------------------------------------------- view
  const svgUrl = useMemo(() => (plan ? URL.createObjectURL(new Blob([plan.svg], { type: 'image/svg+xml' })) : null), [plan]);
  useEffect(() => () => {
    if (svgUrl) URL.revokeObjectURL(svgUrl);
  }, [svgUrl]);

  const planProject = plan?.project_id ? projects.find((p) => p.id === plan.project_id) : null;
  const chatting = turns.length > 0 || Boolean(plan) || Boolean(planId);
  const lastJob = turns.reduce((n, t, i) => (t.kind === 'job' ? i : n), -1);

  const panel: PanelSpec | null =
    plan && panelOpen
      ? {
          title: plan.name,
          actions: (
            <button
              type="button"
              className="st-pill"
              onClick={() => void openIn3D()}
              disabled={opening3d}
              aria-busy={opening3d}
              title="Build this plan as a 3D house you can walk through"
            >
              <Icon name="cube" small /> {opening3d ? 'Opening…' : 'Open in 3D'}
            </button>
          ),
          body: (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14, height: '100%' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--text-muted)' }}>
                <span style={{ fontFamily: 'var(--font-mono)' }}>
                  v{plan.version}
                  {plan.facing ? ` · ${plan.facing}-facing` : ''}
                  {planProject ? ` · ${planProject.name}` : ''}
                </span>
                {!plan.saved && <span style={{ color: '#fde2b0' }}>· not saved to the database yet</span>}
                <span style={{ flex: 1 }} />
                {plan.history.length > 0 && (
                  <>
                    <button type="button" className="st-pill" disabled={busy} onClick={() => void revert()}>
                      <Icon name="undo" small /> Undo
                    </button>
                    <label className="sr-only" htmlFor="fp-version">
                      Go back to a version
                    </label>
                    <select
                      id="fp-version"
                      className="st-pill"
                      disabled={busy}
                      value=""
                      onChange={(e) => e.target.value && void revert(Number(e.target.value))}
                    >
                      <option value="">Versions…</option>
                      {plan.history.map((h) => (
                        <option key={h.version} value={h.version}>
                          v{h.version}
                          {h.change ? ` (before "${h.change.slice(0, 36)}")` : ''}
                        </option>
                      ))}
                    </select>
                  </>
                )}
              </div>
              <div style={{ flex: 1, minHeight: 420 }}>
                <PlanViewer2D svg={plan.svg} title={plan.name} />
              </div>
              {plan.areas.length > 0 && (
                <div className="fp-areas" style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: 1.5 }}>
                  {plan.areas.map((a) => (
                    <div key={a}>{a}</div>
                  ))}
                </div>
              )}
              <ExportMenu planId={plan.id} />
              {plan.notes.length > 0 && (
                <details style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                  <summary style={{ cursor: 'pointer', color: 'var(--text-2)' }}>Notes about this plan ({plan.notes.length})</summary>
                  <ul style={{ margin: '8px 0 0', paddingLeft: 18 }}>
                    {plan.notes.map((n) => (
                      <li key={n}>{n}</li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          ),
        }
      : null;

  const projectMenu = (
    <ProjectMenu
      project={project}
      projects={projects}
      loading={isLoadingProjects}
      error={projectsError}
      highlight={needProject}
      open={menuOpen}
      onOpenChange={setMenuOpen}
      onChoose={(p) => {
        void selectProject(p);
        setNeedProject(false);
      }}
      onCreate={() => navigate(`/projects/new?next=${encodeURIComponent('/projects/ai-generator')}`)}
      onRetry={() => void fetchProjects()}
    />
  );

  const composer = (
    <Composer
      value={draft}
      onChange={(v) => {
        setDraft(v);
        if (composerError) setComposerError(false);
      }}
      onSubmit={() => submit()}
      label={plan ? 'Ask for a change' : 'Describe the house'}
      placeholder={
        plan
          ? 'Ask for a change: “make it east facing”, “bigger kitchen”, “undo”…'
          : parsed && !parsed.ready
            ? 'Add what is missing, e.g. “plot 30 x 40 ft”'
            : 'Describe the house: plot size, rooms, facing, pool…'
      }
      busy={busy || generating}
      error={composerError}
      tools={plan ? null : projectMenu}
      autoFocus
    />
  );

  return (
    <StudioShell
      theme="blueprint"
      agent="plan"
      currentId={plan?.id ?? planId}
      title={plan ? plan.name : chatting ? 'New floor plan' : undefined}
      meta={plan ? `v${plan.version}` : project ? project.name : undefined}
      chatting={chatting}
      topActions={
        plan && !panelOpen ? (
          <button type="button" className="st-pill" onClick={() => setPanelOpen(true)}>
            <Icon name="plan" small /> Show plan
          </button>
        ) : null
      }
      panel={panel}
      onClosePanel={() => setPanelOpen(false)}
    >
      <StudioSync {...signals} />
      {!chatting ? (
        <EmptyState composer={composer} onPick={(p) => setDraft(p)} project={project?.name ?? null} paused={draft.trim() !== ''} />
      ) : (
        <>
          <Thread stamp={`${turns.length}-${plan?.messages.length ?? 0}-${thinking}-${progress.events.length}-${pendingUser}`}>
            {turns.map((t, i) => {
              if (t.kind === 'user') return <UserMessage key={i} text={t.text} />;
              if (t.kind === 'note') return <AiMessage key={i} text={t.text} tone={t.tone} />;
              if (t.kind === 'brief') {
                const latest = t.parsed === parsed && !plan && !jobId;
                return (
                  <AiMessage key={i}>
                    <ConfirmationCard
                      parsed={t.parsed}
                      busy={busy || !latest}
                      onBack={() => setDraft('')}
                      onGenerate={() => void generate()}
                      names={latest ? { project: names.project || project?.name || '', owner: names.owner } : { project: t.parsed.brief.project_name, owner: t.parsed.brief.owner_name }}
                      onNames={latest ? setNames : undefined}
                      footer={
                        latest && t.parsed.ready && !project ? (
                          <p className="st-names-hint" style={{ color: '#fde2b0', margin: 0 }}>
                            Choose the project to save it in (below the message box) before generating.
                          </p>
                        ) : latest && !t.parsed.ready ? (
                          <>
                            {t.parsed.missing.some((m) => m.includes('built-up area')) && (
                              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                                <button type="button" className="st-btn" onClick={() => submit('The area I gave is the plot area.')}>
                                  It is the plot area
                                </button>
                                <button type="button" className="st-btn" onClick={() => submit('The area I gave is the built-up area.')}>
                                  It is the built-up area
                                </button>
                              </div>
                            )}
                            <p className="st-names-hint" style={{ margin: 0 }}>
                              Tell me what is missing in the message box and I will update the brief.
                            </p>
                          </>
                        ) : null
                      }
                    />
                  </AiMessage>
                );
              }
              // a generation job: the orb while it runs, the reason if it fails, nothing once done
              if (i !== lastJob) return null;
              const ev = progress.latest;
              if (ev?.status === 'failed') {
                return (
                  <AiMessage key={i} tone="error" text={`I could not make this plan. ${ev.error ?? ''}`.trim()}>
                    {ev.options.length > 0 && (
                      <ul className="st-fail-list">
                        {ev.options.map((o) => (
                          <li key={o}>{o}</li>
                        ))}
                      </ul>
                    )}
                    <button
                      type="button"
                      className="st-btn"
                      style={{ marginTop: 10 }}
                      onClick={() => {
                        setJobId(null);
                        setDraft(briefText);
                      }}
                    >
                      <Icon name="pen" small />
                      Change the brief and try again
                    </button>
                  </AiMessage>
                );
              }
              return generating ? <Typing key={i} label={ev?.detail || 'Drawing the plan'} /> : null;
            })}

            {loadingPlan && <Typing label="Opening the plan" />}

            {plan && (
              <>
                <AiMessage text={`Here is **${plan.name}**. Ask me to change anything: room sizes, the direction it faces, doors, windows, or say “undo”.`}>
                  <ArtifactCard
                    title={plan.name}
                    meta={`2D floor plan · v${plan.version}${plan.facing ? ` · ${plan.facing}-facing` : ''}`}
                    thumb={svgUrl}
                    open={panelOpen}
                    onOpen={() => setPanelOpen(true)}
                  />
                </AiMessage>
                {plan.messages.map((m, i) =>
                  m.role === 'user' ? (
                    <UserMessage key={`m${i}`} text={m.text} />
                  ) : (
                    <AiMessage
                      key={`m${i}`}
                      text={m.text}
                      tone={m.status === 'impossible' || m.status === 'failed' ? 'error' : m.status === 'needs_clarification' ? 'warn' : undefined}
                    />
                  ),
                )}
                {plan.messages.length === 0 && !pendingUser && (
                  <QuickReplies options={EDIT_IDEAS} disabled={busy} onPick={(o) => submit(o)} />
                )}
              </>
            )}
            {pendingUser && <UserMessage text={pendingUser} />}
            {thinking && <Typing label={thinking} />}
          </Thread>
          <Dock>{composer}</Dock>
        </>
      )}
    </StudioShell>
  );
}

function EmptyState(p: { composer: ReactNode; onPick: (prompt: string) => void; project: string | null; paused: boolean }) {
  const { motionOn, userName } = useStudio();
  return (
    <Stage footnote="Floor Plan Studio · every wall, door and size is checked by code before it is shown">
      <Headline name={userName} lines={LINES} playing={motionOn} paused={p.paused} />
      {p.composer}
      <Chips items={STARTERS} onPick={p.onPick} />
      {!p.project && <Status>Choose or create the project this plan belongs to with the <strong>Choose project</strong> button.</Status>}
    </Stage>
  );
}
