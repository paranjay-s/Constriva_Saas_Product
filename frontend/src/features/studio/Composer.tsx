/**
 * The glass prompt composer: Enter sends, Shift+Enter adds a line, grows with the text.
 * Attach, project picker and other tools are passed in; voice input is built in.
 */
import { type ReactNode, useCallback, useEffect, useRef } from 'react';
import { useSpeechInput } from '../floorplan/hooks/useSpeechInput';
import { Icon } from './icons';
import { useOcean } from './ocean/OceanBackground';

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  placeholder: string;
  label: string;
  busy?: boolean;
  /** Something besides text makes it sendable (an attached photo). */
  ready?: boolean;
  error?: boolean;
  attachments?: ReactNode;
  tools?: ReactNode;
  onAttach?: () => void;
  attachLabel?: string;
  hint?: string;
  autoFocus?: boolean;
}

export function Composer(p: Props) {
  const ocean = useOcean();
  const box = useRef<HTMLFormElement>(null);
  const area = useRef<HTMLTextAreaElement>(null);
  const valueRef = useRef(p.value);
  valueRef.current = p.value;
  const { onChange } = p;

  const append = useCallback(
    (t: string) => {
      const cur = valueRef.current;
      onChange(cur ? `${cur.trimEnd()} ${t}` : t);
    },
    [onChange],
  );
  const speech = useSpeechInput(append);

  useEffect(() => {
    ocean.setTarget(box.current);
  }, [ocean]);

  useEffect(() => {
    const el = area.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 224)}px`;
  }, [p.value]);

  useEffect(() => {
    if (p.autoFocus) area.current?.focus();
  }, [p.autoFocus]);

  const sendable = !p.busy && (p.value.trim().length > 0 || Boolean(p.ready));

  return (
    <form
      ref={box}
      className={`st-composer${p.error ? ' is-error' : ''}`}
      data-ready={sendable ? '' : undefined}
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        speech.stop();
        p.onSubmit();
      }}
    >
      {p.attachments}
      <label className="sr-only" htmlFor="st-prompt">
        {p.label}
      </label>
      <textarea
        ref={area}
        id="st-prompt"
        rows={1}
        maxLength={4000}
        value={p.value}
        placeholder={p.placeholder}
        autoComplete="off"
        aria-invalid={p.error || undefined}
        onChange={(e) => {
          p.onChange(e.target.value);
          ocean.typing();
        }}
        onKeyDown={(e) => {
          if (e.key !== 'Enter' || e.nativeEvent.isComposing) return;
          if (e.shiftKey) return;
          e.preventDefault();
          box.current?.requestSubmit();
        }}
      />
      {speech.listening && (
        <p className="st-hint" style={{ marginTop: 6 }}>
          Listening… {speech.interim}
        </p>
      )}
      {speech.error && (
        <p className="st-hint" style={{ marginTop: 6, color: 'var(--danger)' }}>
          {speech.error}
        </p>
      )}
      <div className="st-toolbar">
        <div className="st-tools">
          {p.onAttach && (
            <button type="button" className="st-tool" aria-label={p.attachLabel ?? 'Attach a file'} title={p.attachLabel ?? 'Attach a file'} onClick={p.onAttach}>
              <Icon name="plus" />
            </button>
          )}
          {p.tools}
          {speech.supported && (
            <button
              type="button"
              className="st-tool"
              aria-pressed={speech.listening}
              aria-label={speech.listening ? 'Stop voice input' : 'Speak instead of typing'}
              title={speech.listening ? 'Stop listening' : 'Speak instead of typing'}
              onClick={speech.listening ? speech.stop : speech.start}
            >
              <Icon name="mic" />
            </button>
          )}
        </div>
        <div className="st-tools">
          <p className="st-hint" aria-hidden="true">
            {p.hint ?? '↵ send · ⇧↵ new line'}
          </p>
          <button type="submit" className="st-send" aria-label="Send" disabled={p.busy}>
            <Icon name="arrow" />
          </button>
        </div>
      </div>
    </form>
  );
}

/** Starting points under the composer (empty state) that fill the prompt. */
export function Chips({ items, onPick }: { items: { cmd: string; prompt: string }[]; onPick: (prompt: string) => void }) {
  return (
    <ul className="st-chips" aria-label="Starting points">
      {items.map((c) => (
        <li key={c.cmd}>
          <button type="button" className="st-chip" onClick={() => onPick(c.prompt)}>
            <span className="st-slash" aria-hidden="true">
              /
            </span>
            {c.cmd}
          </button>
        </li>
      ))}
    </ul>
  );
}
