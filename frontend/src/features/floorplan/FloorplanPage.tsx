/**
 * AI floor plan generator: brief -> confirmation -> live progress -> plan + chat edits.
 *
 * The plan id is kept in the URL (?plan=...), so a reload or a shared link reopens the
 * same plan. "Open in 3D" hands the plan's PlanJSON to the existing 3D workspace.
 */
import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '../../components/ui/Button';
import { IconArrowRight, IconRefresh } from '../../components/ui/Icons';
import { useProject } from '../../context/ProjectContext';
import { ApiError } from '../../lib/api';
import type { PlanJSON } from '../../types';
import { floorplanApi } from './api';
import { BriefForm } from './components/BriefForm';
import { ConfirmationCard } from './components/ConfirmationCard';
import { EditChat } from './components/EditChat';
import { ExportMenu } from './components/ExportMenu';
import { PlanViewer2D } from './components/PlanViewer2D';
import { ProgressSteps } from './components/ProgressSteps';
import { useJobEvents } from './hooks/useJobEvents';
import { type BriefFormInput, type BriefFormValues, type ChatMessage, EMPTY_FORM, type ParseResponse, type PlanResponse } from './schemas';

type Step = 'form' | 'confirm' | 'generating' | 'plan';

function errorText(e: unknown): string {
  if (e instanceof ApiError) return e.detail;
  if (e instanceof Error) return e.message;
  return 'Something went wrong.';
}

export function FloorplanPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const { activeProject, setPlanData, setProjectStatus } = useProject();

  const [step, setStep] = useState<Step>(params.get('plan') ? 'plan' : 'form');
  const [formValues, setFormValues] = useState<BriefFormInput>(EMPTY_FORM);
  const [parsed, setParsed] = useState<ParseResponse | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chatBusy, setChatBusy] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [pending, setPending] = useState<ChatMessage | null>(null);

  const progress = useJobEvents(step === 'generating' ? jobId : null);
  const planId = params.get('plan');

  const loadPlan = useCallback(
    async (id: string) => {
      setBusy(true);
      setError(null);
      try {
        setPlan(await floorplanApi.plan(id));
        setStep('plan');
      } catch (e) {
        setError(errorText(e));
        setStep('form');
        setParams({}, { replace: true });
      } finally {
        setBusy(false);
      }
    },
    [setParams],
  );

  // Open the plan named in the URL (after generating, on reload, or from a shared link).
  useEffect(() => {
    if (!planId || plan?.id === planId) return;
    const req = { cancelled: false };
    floorplanApi
      .plan(planId)
      .then((p) => {
        if (req.cancelled) return;
        setPlan(p);
        setStep('plan');
      })
      .catch((e: unknown) => {
        if (req.cancelled) return;
        setError(errorText(e));
        setStep('form');
        setParams({}, { replace: true });
      });
    return () => {
      req.cancelled = true;
    };
  }, [planId, plan?.id, setParams]);
  const loadingPlan = Boolean(planId) && plan?.id !== planId;

  useEffect(() => {
    const ev = progress.latest;
    if (step === 'generating' && ev?.status === 'done' && ev.plan_id) {
      setParams({ plan: ev.plan_id });
    }
  }, [progress.latest, step, setParams]);

  const submitForm = async (values: BriefFormValues) => {
    setFormValues({ ...values, bedrooms: values.bedrooms, bathrooms: values.bathrooms });
    setBusy(true);
    setError(null);
    try {
      setParsed(await floorplanApi.parseBrief(values));
      setStep('confirm');
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const generate = async () => {
    if (!parsed) return;
    setBusy(true);
    setError(null);
    try {
      setJobId(await floorplanApi.generate(parsed.brief, activeProject?.id));
      setStep('generating');
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const sendEdit = async (text: string) => {
    if (!plan) return;
    setChatBusy(true);
    setChatError(null);
    setPending({ role: 'user', text });
    try {
      const res = await floorplanApi.edit(plan.id, text, plan.version);
      setPlan(res.plan);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setChatError('The plan was changed somewhere else; reloaded the latest version. Please send again.');
        void loadPlan(plan.id);
      } else {
        setChatError(errorText(e));
      }
    } finally {
      setPending(null);
      setChatBusy(false);
    }
  };

  const startOver = () => {
    setParams({});
    setPlan(null);
    setParsed(null);
    setJobId(null);
    setStep('form');
  };

  const openIn3D = () => {
    if (!plan) return;
    const planJson = plan.plan_json as unknown as PlanJSON;
    setPlanData(planJson);
    try {
      if (activeProject?.id) localStorage.setItem(`construtiva_plan_cache_${activeProject.id}`, JSON.stringify(planJson));
    } catch {
      // storage full: the context copy is enough for this session
    }
    setProjectStatus('ready');
    navigate('/projects/3d-workspace');
  };

  const messages = pending && plan ? [...plan.messages, pending] : (plan?.messages ?? []);

  return (
    <div className="flex min-h-screen flex-col bg-[#111317] font-sans text-white">
      <header className="sticky top-0 z-30 flex flex-wrap items-center justify-between gap-3 border-b border-white/10 bg-[#0d0f12]/90 px-4 py-3 backdrop-blur-md sm:px-6">
        <div>
          <h1 className="text-base font-semibold tracking-tight">AI Floor Plan Generator</h1>
          <p className="text-xs text-[#7D8594]">
            Describe the house, check the brief, then change the plan by chat.
          </p>
        </div>
        {step === 'plan' && plan && (
          <div className="flex flex-wrap items-center gap-2">
            <ExportMenu planId={plan.id} />
            <Button size="sm" variant="secondary" onClick={startOver} leftIcon={<IconRefresh className="h-4 w-4" />}>
              New plan
            </Button>
            <Button size="sm" variant="accent" onClick={openIn3D} rightIcon={<IconArrowRight className="h-4 w-4" />}>
              Open in 3D
            </Button>
          </div>
        )}
      </header>

      <main className="flex flex-1 flex-col lg:flex-row lg:overflow-hidden">
        <section className="flex flex-col gap-4 border-b border-[#23272F] bg-[#16181E] p-4 sm:p-6 lg:w-[400px] lg:shrink-0 lg:overflow-y-auto lg:border-b-0 lg:border-r">
          {error && (
            <div role="alert" className="rounded-md border border-[#E5484D]/40 bg-[#E5484D]/10 p-3 text-sm text-[#FFDAD6]">
              {error}
            </div>
          )}
          {step === 'form' && <BriefForm defaultValues={formValues} busy={busy} onSubmit={submitForm} />}
          {step === 'confirm' && parsed && (
            <ConfirmationCard parsed={parsed} busy={busy} onBack={() => setStep('form')} onGenerate={generate} />
          )}
          {step === 'generating' && <ProgressSteps events={progress.events} onRetry={() => setStep('form')} />}
          {step === 'plan' && plan && (
            <>
              <div>
                <h2 className="text-sm font-semibold">{plan.name}</h2>
                <p className="text-xs text-[#7D8594]">
                  Version {plan.version}
                  {!plan.saved && ' · not saved to the database (kept until the server restarts)'}
                </p>
              </div>
              {plan.notes.length > 0 && (
                <details className="rounded-md border border-[#23272F] bg-[#0F1115] p-3 text-xs text-[#9AA3B2]">
                  <summary className="cursor-pointer text-[#D5DAE1]">Notes about this plan ({plan.notes.length})</summary>
                  <ul className="mt-2 list-disc space-y-0.5 pl-4">
                    {plan.notes.map((n) => (
                      <li key={n}>{n}</li>
                    ))}
                  </ul>
                </details>
              )}
              <EditChat messages={messages} busy={chatBusy} error={chatError} onSend={sendEdit} />
            </>
          )}
          {step === 'plan' && loadingPlan && <p className="text-sm text-[#7D8594]">Loading the plan…</p>}
        </section>

        <section className="flex min-h-[480px] flex-1 p-4 sm:p-6">
          {plan && step === 'plan' ? (
            <PlanViewer2D svg={plan.svg} title={plan.name} />
          ) : (
            <div className="flex h-full w-full items-center justify-center rounded-lg border border-dashed border-[#2A2F38] text-center text-sm text-[#5C6370]">
              <p className="max-w-xs">
                {step === 'generating'
                  ? 'Your plan is being made. Every wall, door and room size is checked before it is shown.'
                  : 'The drawing appears here: walls, doors, windows, furniture and room sizes, ready to download as PDF, DXF, SVG or PNG.'}
              </p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
