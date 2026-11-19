/**
 * Shared frame of project creation: step 01 (details, /projects/new) and step 02
 * (floor plan source, /projects/options) are the same screen at different steps.
 */
import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileUp, Spark } from '../dashboard';

const HERO = '/assets/house-bg.webp?v=lantern1';
const STEPS = ['01 Project details', '02 Floor plan source', '03 3D workspace'];

export function ProjectFlow({
  step,
  title,
  left,
  locked,
}: {
  step: 1 | 2;
  title: string;
  left: ReactNode;
  /** step 02 is shown but not usable until the project exists */
  locked: boolean;
}) {
  const navigate = useNavigate();
  const done = step === 1 ? 3 : 50;

  return (
    <>
      <div className="cv-hero cv-fade">
        <div className="cv-hero-mask">
          <img src={HERO} alt="" aria-hidden="true" style={{ filter: 'grayscale(1) brightness(.42) contrast(1.15)' }} />
          <img className="cv-reveal" src={HERO} alt="A villa appearing in full colour: two storeys of sand stone with glowing patterned screens and a dark reflecting pool" />
          <div
            className="cv-edge"
            aria-hidden="true"
            style={{
              position: 'absolute',
              top: '4%',
              bottom: '8%',
              width: 2,
              background: 'linear-gradient(180deg, rgba(191,246,251,0), #bff6fb 20%, #ffffff 50%, #bff6fb 80%, rgba(191,246,251,0))',
              boxShadow: '0 0 18px 2px rgba(124,232,242,.75)',
            }}
          />
        </div>
      </div>
      <div className="cv-scrim" aria-hidden="true" />

      <main className="cv-main">
        <section className="cv-col cv-new-left">
          <div className="cv-title cv-rise">
            <h1>{title}</h1>
            <p className="cv-sub">{step === 1 ? 'step 01 · project details' : 'step 02 · floor plan source'}</p>
          </div>
          {left}
        </section>

        <section className="cv-col cv-new-mid">
          <div className="cv-spacer" />
          <div className="cv-stepper cv-rise" style={{ ['--d' as string]: '.6s' }} role="group" aria-label={`Step ${step} of 3`}>
            <div className="cv-track" aria-hidden="true">
              <i />
              <i className="is-done" style={{ width: `${done}%` }} />
              <span className={step === 1 ? 'is-now cv-pulse' : 'is-done'} style={{ left: 6 }} />
              <span className={step === 2 ? 'is-now cv-pulse' : ''} style={{ left: '50%' }} />
              <span style={{ left: 'calc(100% - 6px)' }} />
            </div>
            <div className="cv-steps">
              {STEPS.map((s, i) => (
                <span key={s} className={i + 1 === step ? 'is-now' : undefined} aria-current={i + 1 === step ? 'step' : undefined}>
                  {s}
                </span>
              ))}
            </div>
          </div>
        </section>

        <section className="cv-col cv-new-right" aria-label="Floor plan source">
          {step === 1 && (
            <p className="cv-sub cv-rise" style={{ ['--d' as string]: '.3s', margin: '14px 6px 0' }}>
              step 02 · floor plan source
            </p>
          )}
          <div className="cv-card cv-option cv-rise" data-locked={locked} style={{ ['--d' as string]: '.4s' }}>
            <div className="cv-between">
              <span className="cv-option-icon">
                <FileUp />
              </span>
              <span className="cv-note" style={{ fontSize: 11 }}>
                OPTION 01 · FILE UPLOAD
              </span>
            </div>
            <h2>Import existing 2D plan</h2>
            <p>Upload the architectural PDF. It is read and opened in the 3D workspace.</p>
            <button type="button" className="cv-btn" disabled={locked} onClick={() => navigate('/projects/import')}>
              Import PDF drawing
            </button>
          </div>
          <div className="cv-card cv-option is-ai cv-rise" data-locked={locked} style={{ ['--d' as string]: '.5s' }}>
            <div className="cv-between">
              <span className="cv-option-icon">
                <Spark />
              </span>
              <span className="cv-note" style={{ fontSize: 11 }}>
                OPTION 02 · AI SYNTHESIS
              </span>
            </div>
            <h2>Create your own 2D plan</h2>
            <p>Describe the plot and rooms in the floor plan chat. The plan is saved in this project.</p>
            <button type="button" className="cv-btn cv-btn-primary" disabled={locked} onClick={() => navigate('/projects/ai-generator')}>
              Launch AI plan generator
            </button>
          </div>
          {locked && step === 1 && <p className="cv-note" style={{ margin: '0 6px' }}>Available once the project is created.</p>}
        </section>
      </main>
    </>
  );
}
