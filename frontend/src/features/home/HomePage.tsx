/**
 * Route /home: project overview. Everything shown is read from the backend: the user's
 * projects, the 2D floor plans in each, and the image analyses.
 */
import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useProject } from '../../context/ProjectContext';
import type { Project } from '../../types';
import {
  ArrowRight,
  DashedRing,
  PhotoIcon,
  PlanIcon,
  Plus,
  Refresh,
  Skyline,
  Trash,
  dayLabel,
  plural,
  shortDate,
} from '../dashboard';
import { type FloorplanSummary, floorplanApi } from '../floorplan';
import { materialApi } from '../materials';
import type { SessionSummary } from '../materials/schemas';

const HERO = '/assets/house-bg.webp?v=lantern1';
const PLANS_SHOWN = 3;
const CHATS_SHOWN = 3;

type Chat =
  | { kind: 'plan'; id: string; title: string; meta: string; at: string; plan: FloorplanSummary }
  | { kind: 'image'; id: string; title: string; meta: string; at: string };

const errorText = (err: unknown, fallback: string) => (err instanceof Error && err.message ? err.message : fallback);

export function HomePage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { projects, isLoadingProjects, projectsError, fetchProjects, selectProject, deleteProject, activeProject } =
    useProject();

  const [plans, setPlans] = useState<FloorplanSummary[] | null>(null);
  const [plansError, setPlansError] = useState<string | null>(null);
  const [analyses, setAnalyses] = useState<SessionSummary[] | null>(null);
  const [analysesError, setAnalysesError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  // a project opened from the bottom of a long list would otherwise be half out of view
  useEffect(() => {
    if (openId) document.getElementById(`cv-project-${openId}`)?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' });
  }, [openId]);

  const load = () => {
    void fetchProjects();
    floorplanApi
      .list()
      .then((list) => {
        setPlans(list);
        setPlansError(null);
      })
      .catch((err) => setPlansError(errorText(err, 'Floor plans could not be loaded.')));
    materialApi
      .list()
      .then((list) => {
        setAnalyses(list);
        setAnalysesError(null);
      })
      .catch((err) => setAnalysesError(errorText(err, 'Image analyses could not be loaded.')));
  };
  useEffect(load, []); // eslint-disable-line react-hooks/exhaustive-deps

  const plansByProject = useMemo(() => {
    const grouped: Record<string, FloorplanSummary[]> = {};
    for (const p of plans ?? []) if (p.project_id) (grouped[p.project_id] ??= []).push(p);
    return grouped;
  }, [plans]);

  const skyline = useMemo(
    () => projects.map((p) => ({ id: p.id, name: p.name, plans: plansByProject[p.id]?.length ?? 0 })),
    [projects, plansByProject],
  );

  const chats = useMemo<Chat[]>(() => {
    const all: Chat[] = [
      ...(plans ?? []).map(
        (p): Chat => ({
          kind: 'plan',
          id: p.id,
          title: p.name,
          meta: [`v${p.version}`, dayLabel(p.created_at)].filter(Boolean).join(' · '),
          at: p.created_at,
          plan: p,
        }),
      ),
      ...(analyses ?? []).map(
        (a): Chat => ({
          kind: 'image',
          id: a.id,
          title: a.title || a.scene || 'Image analysis',
          meta: [a.materials != null ? plural(a.materials, 'material') : '', dayLabel(a.created_at)]
            .filter(Boolean)
            .join(' · '),
          at: a.created_at,
        }),
      ),
    ];
    return all.sort((a, b) => b.at.localeCompare(a.at)).slice(0, CHATS_SHOWN);
  }, [plans, analyses]);

  // the expanded card: the one the user opened, else the active project, else the newest
  const expanded =
    projects.find((p) => p.id === openId) ?? projects.find((p) => p.id === activeProject?.id) ?? projects[0] ?? null;

  const openChat = (c: Chat) => {
    if (c.kind === 'image') {
      navigate(`/materials/analyse?analysis=${encodeURIComponent(c.id)}`);
      return;
    }
    const owner = projects.find((p) => p.id === c.plan.project_id);
    if (owner) void selectProject(owner);
    navigate(`/projects/ai-generator?plan=${encodeURIComponent(c.id)}`);
  };

  const openPlan = (project: Project, planId: string) => {
    void selectProject(project);
    navigate(`/projects/ai-generator?plan=${encodeURIComponent(planId)}`);
  };

  const newPlan = (project: Project) => {
    void selectProject(project);
    navigate('/projects/ai-generator');
  };

  const enterWorkspace = async (project: Project) => {
    await selectProject(project);
    navigate('/projects/3d-workspace');
  };

  const remove = async (project: Project) => {
    if (window.confirm(`Delete the project "${project.name}"? This cannot be undone.`)) {
      await deleteProject(project.id);
    }
  };

  const loadingProjects = isLoadingProjects && projects.length === 0;
  const today = shortDate(new Date());

  return (
    <>
      <div className="cv-hero cv-fade">
        <div className="cv-hero-mask cv-breathe">
          <img src={HERO} alt="A two-storey sand-stone villa at dusk with glowing patterned screens, palm trees and a dark reflecting pool" />
          <svg aria-hidden="true" viewBox="0 0 736 736" preserveAspectRatio="xMidYMid slice">
            <defs>
              <linearGradient id="cvScan" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stopColor="#7ce8f2" stopOpacity="0" />
                <stop offset=".85" stopColor="#bff6fb" stopOpacity=".22" />
                <stop offset="1" stopColor="#ffffff" stopOpacity=".75" />
              </linearGradient>
            </defs>
            <rect className="cv-scan" x="0" y="0" width="736" height="34" fill="url(#cvScan)" style={{ mixBlendMode: 'screen' }} />
            <path className="cv-march" d="M175 205 L500 118 L420 278 M500 118 L540 400 L200 395 L175 205" fill="none" stroke="rgba(255,255,255,.7)" strokeWidth="1" strokeDasharray="2 6" strokeLinecap="round" />
            <g fill="rgba(4,6,10,.3)" stroke="#ffffff" strokeWidth="1.1" strokeDasharray="2.5 2.5">
              {[
                [167, 197, 0],
                [492, 110, -2],
                [412, 270, -3.4],
                [532, 392, -1.2],
                [192, 387, -4.4],
              ].map(([x, y, d]) => (
                <rect key={`${x}-${y}`} className="cv-drift" x={x} y={y} width="16" height="16" style={{ ['--d' as string]: `${d}s` }} />
              ))}
            </g>
          </svg>
        </div>
      </div>
      <div className="cv-scrim" aria-hidden="true" />

      <main className="cv-main">
        <section className="cv-col cv-ov-left">
          <div className="cv-title cv-rise">
            <h1>Project overview</h1>
            <p className="cv-sub">{[today, user?.name].filter(Boolean).join(' · ')}</p>
          </div>

          <div className="cv-card cv-sky cv-rise" style={{ ['--d' as string]: '.15s' }}>
            <div className="cv-between" style={{ alignItems: 'flex-end' }}>
              <div className="cv-sky-count">
                <b data-testid="count-projects">{loadingProjects ? '–' : projects.length}</b>
                <span>{projects.length === 1 ? 'project' : 'projects'}</span>
              </div>
              <div className="cv-pills">
                <span data-testid="count-plans">{plans ? plural(plans.length, 'floor plan') : 'floor plans: –'}</span>
                <span className="is-alt" data-testid="count-analyses">
                  {analyses ? plural(analyses.length, 'image analysis', 'image analyses') : 'image analyses: –'}
                </span>
              </div>
            </div>
            <Skyline projects={skyline} analyses={analyses?.length ?? 0} />
            <p className="cv-legend">building = project · floor = 2D plan · frame = image analysis</p>
          </div>

          <div className="cv-duo cv-rise" style={{ ['--d' as string]: '.25s' }}>
            <Link to="/projects/ai-generator" className="cv-tile is-primary">
              <PlanIcon />
              Floor plan chat
            </Link>
            <Link to="/materials/analyse" className="cv-tile">
              <PhotoIcon />
              Image analysis
            </Link>
          </div>

          <div className="cv-card cv-card-glow cv-push cv-rise" style={{ ['--d' as string]: '.35s' }}>
            <h2 className="cv-h2" style={{ marginBottom: 8 }}>
              Recent chats
            </h2>
            {plansError && <p className="cv-error">{plansError}</p>}
            {analysesError && <p className="cv-error" style={{ marginTop: 6 }}>{analysesError}</p>}
            {plans === null && analyses === null && !plansError && !analysesError ? (
              <p className="cv-state">Loading your chats…</p>
            ) : chats.length === 0 && !plansError && !analysesError ? (
              <p className="cv-state">No chats yet. Start a floor plan or analyse a photo.</p>
            ) : (
              chats.map((c) => (
                <button key={`${c.kind}-${c.id}`} type="button" className="cv-chat" onClick={() => openChat(c)}>
                  <span className={c.kind === 'plan' ? 'cv-tag' : 'cv-tag is-alt'}>{c.kind === 'plan' ? 'PLAN' : 'IMAGE'}</span>
                  <span className="cv-chat-body">
                    <b>{c.title}</b>
                    <small>{c.meta}</small>
                  </span>
                </button>
              ))
            )}
          </div>
        </section>

        <section className="cv-col cv-ov-mid">
          <div className="cv-spacer" />
          <div className="cv-create cv-rise" style={{ ['--d' as string]: '.7s' }}>
            <Link to="/projects/new" className="cv-create-pill">
              <span>
                <DashedRing className="cv-pulse" style={{ color: 'var(--cv-ac)' }} />
                Create new project
              </span>
              <span className="cv-create-plus" aria-hidden="true">
                <Plus />
              </span>
            </Link>
          </div>
        </section>

        <section className="cv-col cv-ov-right">
          <div className="cv-card cv-push cv-rise" style={{ ['--d' as string]: '.25s' }}>
            <div className="cv-between">
              <h2 className="cv-h2">Your projects</h2>
              <span className="cv-between" style={{ gap: 4 }}>
                <span className="cv-note">{loadingProjects ? 'loading' : plural(projects.length, 'project')}</span>
                <button type="button" className="cv-icon-btn" aria-label="Refresh projects" disabled={isLoadingProjects} onClick={load}>
                  <Refresh size={16} className={isLoadingProjects ? 'cv-spin' : undefined} />
                </button>
              </span>
            </div>

            {projectsError && <p className="cv-error" style={{ marginTop: 10 }}>{projectsError}</p>}

            {loadingProjects ? (
              <p className="cv-state">Loading your projects…</p>
            ) : projects.length === 0 ? (
              !projectsError && (
                <div className="cv-state">
                  <p>No projects yet.</p>
                  <Link to="/projects/new" className="cv-btn cv-btn-primary" style={{ marginTop: 12 }}>
                    Create first project
                  </Link>
                </div>
              )
            ) : (
              <div className="cv-projects">
                {projects.map((proj) => {
                  const own = plansByProject[proj.id] ?? [];
                  if (proj.id !== expanded?.id) {
                    return (
                      <button key={proj.id} type="button" className="cv-proj-row" aria-expanded="false" onClick={() => setOpenId(proj.id)}>
                        <span style={{ minWidth: 0 }}>
                          <b>{proj.name}</b>
                          <small>
                            {proj.type} · {proj.status} · {own.length === 0 ? 'no plans yet' : plural(own.length, 'plan')}
                          </small>
                        </span>
                        <span className="cv-note" style={{ flex: 'none' }}>
                          {dayLabel(proj.createdAt)}
                        </span>
                      </button>
                    );
                  }
                  return (
                    <article key={proj.id} id={`cv-project-${proj.id}`} className="cv-proj-open" aria-label={proj.name}>
                      <div className="cv-between">
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                          <span className="cv-badge">{proj.type}</span>
                          <span className="cv-badge is-quiet">{proj.status}</span>
                        </div>
                        <button
                          type="button"
                          className="cv-icon-btn is-danger"
                          style={{ margin: '-8px -8px -8px 0' }}
                          aria-label={`Delete project ${proj.name}`}
                          onClick={() => void remove(proj)}
                        >
                          <Trash />
                        </button>
                      </div>
                      <h3>{proj.name}</h3>
                      {proj.description && <p>{proj.description}</p>}
                      <div className="cv-between" style={{ marginTop: 12 }}>
                        <span className="cv-note" style={{ fontSize: 11, letterSpacing: '.05em' }}>
                          2D FLOOR PLANS ({own.length})
                        </span>
                        <button type="button" className="cv-link" style={{ margin: '-10px 0', fontSize: 13 }} onClick={() => newPlan(proj)}>
                          + New 2D plan
                        </button>
                      </div>
                      {own.slice(0, PLANS_SHOWN).map((fp) => (
                        <button key={fp.id} type="button" className="cv-plan" onClick={() => openPlan(proj, fp.id)}>
                          <span>{fp.name}</span>
                          <span>v{fp.version} · Open</span>
                        </button>
                      ))}
                      {own.length > PLANS_SHOWN && (
                        <p className="cv-note" style={{ marginTop: 6, fontSize: 11 }}>
                          +{own.length - PLANS_SHOWN} more
                        </p>
                      )}
                      <div className="cv-between" style={{ marginTop: 12 }}>
                        <span className="cv-note" style={{ fontSize: 11 }}>
                          {dayLabel(proj.createdAt)}
                        </span>
                        <button type="button" className="cv-link" style={{ fontWeight: 500 }} onClick={() => void enterWorkspace(proj)}>
                          Enter workspace
                          <ArrowRight size={16} />
                        </button>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </div>
        </section>
      </main>
    </>
  );
}
