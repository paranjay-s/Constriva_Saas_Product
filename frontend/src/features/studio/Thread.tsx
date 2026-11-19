/**
 * The conversation: user bubbles on the right, assistant replies on the left with a small
 * mark, quick replies, a typing indicator and cards (progress, results) inside replies.
 * Assistant text supports paragraphs, "- " bullets and **bold** (nothing else is parsed).
 */
import { Fragment, type ReactNode, useEffect, useRef } from 'react';
import { Icon, type IconName } from './icons';
import { PlasmaOrb } from './PlasmaOrb';

function Inline({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\*\*[^*]+\*\*)/g).map((p, i) =>
        p.startsWith('**') && p.endsWith('**') ? <strong key={i}>{p.slice(2, -2)}</strong> : <Fragment key={i}>{p}</Fragment>,
      )}
    </>
  );
}

export function RichText({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let bullets: string[] = [];
  const flush = () => {
    if (!bullets.length) return;
    blocks.push(
      <ul key={`u${blocks.length}`}>
        {bullets.map((b, i) => (
          <li key={i}>
            <Inline text={b} />
          </li>
        ))}
      </ul>,
    );
    bullets = [];
  };
  for (const line of text.split('\n')) {
    const m = /^\s*[-•]\s+(.*)$/.exec(line);
    if (m) {
      bullets.push(m[1]);
      continue;
    }
    flush();
    if (line.trim()) {
      blocks.push(
        <p key={`p${blocks.length}`}>
          <Inline text={line} />
        </p>,
      );
    }
  }
  flush();
  return <>{blocks}</>;
}

export function UserMessage({ text, images }: { text: string; images?: string[] }) {
  return (
    <div className="st-msg-user">
      {images && images.length > 0 && (
        <div className="st-attach-row">
          {images.map((src, i) => (
            <img key={i} src={src} alt={`Attached photo ${i + 1}`} />
          ))}
        </div>
      )}
      {text}
    </div>
  );
}

export function AiMessage({
  children,
  text,
  tone,
  icon = 'spark',
}: {
  children?: ReactNode;
  text?: string;
  tone?: 'error' | 'warn';
  icon?: IconName;
}) {
  return (
    <div className="st-msg-ai">
      <span className="st-ai-mark" aria-hidden="true">
        <Icon name={icon} small />
      </span>
      <div className="st-ai-body" data-tone={tone}>
        {text && <RichText text={text} />}
        {children}
      </div>
    </div>
  );
}

export function QuickReplies({ options, onPick, disabled }: { options: string[]; onPick: (o: string) => void; disabled?: boolean }) {
  if (!options.length) return null;
  return (
    <div className="st-replies">
      {options.map((o) => (
        <button key={o} type="button" className="st-reply" disabled={disabled} onClick={() => onPick(o)}>
          {o}
        </button>
      ))}
    </div>
  );
}

/** The AI is working: the plasma orb and what it is doing. Unmounted as soon as the answer arrives. */
export function Typing({ label }: { label: string }) {
  return (
    <div className="st-msg-ai st-thinking" role="status" aria-live="polite">
      <PlasmaOrb size={92} />
      <span className="st-thinking-label">{label}</span>
    </div>
  );
}

/** Opens the side panel (a plan drawing, the material results). */
export function ArtifactCard({
  title,
  meta,
  thumb,
  icon,
  onOpen,
  open,
}: {
  title: string;
  meta: string;
  thumb?: string | null;
  icon?: IconName;
  onOpen: () => void;
  open?: boolean;
}) {
  return (
    <button type="button" className="st-artifact" onClick={onOpen} aria-pressed={open}>
      <span className="st-artifact-thumb" data-dark={thumb ? undefined : ''}>
        {thumb ? <img src={thumb} alt="" /> : <Icon name={icon ?? 'plan'} />}
      </span>
      <span className="st-artifact-meta">
        <strong>{title}</strong>
        <span>{meta}</span>
      </span>
      <span className="st-open">
        <Icon name="maximize" small />
        {open ? 'Open' : 'View'}
      </span>
    </button>
  );
}

/** Scrolls to the newest message whenever `stamp` changes. */
export function Thread({ children, stamp }: { children: ReactNode; stamp: unknown }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: 'end' });
  }, [stamp]);
  return (
    <div className="st-thread" aria-live="polite">
      <div className="st-thread-inner">
        {children}
        <div ref={end} />
      </div>
    </div>
  );
}
