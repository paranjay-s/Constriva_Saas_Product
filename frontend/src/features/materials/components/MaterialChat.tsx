/**
 * Follow-up chat in the style of modern assistants: user bubbles on the right, plain
 * assistant replies on the left, quick-answer chips, a typing indicator and one rounded
 * composer with attach (floor plan) and send.
 */
import { Fragment, useEffect, useRef, useState } from 'react';
import { IconSparkles, SendIcon as IconSend } from '../../../components/ui/Icons';
import type { ChatMessage } from '../schemas';

interface Props {
  messages: ChatMessage[];
  pendingOptions: string[];
  usingLabel?: string | null;
  busy: boolean;
  /** Shown as a typing indicator while the assistant works ("Reading the floor plan"). */
  thinking?: string | null;
  onSend: (message: string, file?: File | null) => void;
  onEditSpace?: () => void;
}

const PLAN_ACCEPT = 'application/pdf,image/png,image/jpeg';
const SUGGESTIONS = [
  'Replicate this design in my floor plan',
  'How much for the kitchen platform? Kitchen is 10 x 8 ft',
  'How did you calculate the quantities?',
  'What can I use instead of this?',
  'What else do I need along with these?',
];

/** One line of text with **bold** spans (nothing else is interpreted). */
function Inline({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((p, i) =>
        p.startsWith('**') && p.endsWith('**') ? (
          <strong key={i} className="font-semibold text-white">
            {p.slice(2, -2)}
          </strong>
        ) : (
          <Fragment key={i}>{p}</Fragment>
        ),
      )}
    </>
  );
}

/** Paragraphs (blank line), "- " bullet lists and **bold**: enough for step-by-step answers. */
function RichText({ text }: { text: string }) {
  const blocks = text.split(/\n\s*\n/);
  return (
    <>
      {blocks.map((block, b) => {
        const lines = block.split('\n').filter((l) => l.trim() !== '');
        const bullets = lines.filter((l) => /^\s*[-•]\s+/.test(l));
        const head = lines.filter((l) => !/^\s*[-•]\s+/.test(l));
        return (
          <div key={b} className={b > 0 ? 'mt-2.5' : ''}>
            {head.map((l, i) => (
              <p key={i}>
                <Inline text={l} />
              </p>
            ))}
            {bullets.length > 0 && (
              <ul className="mt-1 space-y-0.5 pl-4">
                {bullets.map((l, i) => (
                  <li key={i} className="list-disc marker:text-[#5C6370]">
                    <Inline text={l.replace(/^\s*[-•]\s+/, '')} />
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </>
  );
}

function Avatar() {
  return (
    <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#C5A77B]/15 text-[#C5A77B]">
      <IconSparkles className="h-3.5 w-3.5" />
    </span>
  );
}

function Typing({ label }: { label: string }) {
  return (
    <div className="flex items-start gap-3" role="status">
      <Avatar />
      <div className="flex items-center gap-2 pt-1.5 text-sm text-[#9AA3B2]">
        <span className="flex gap-1" aria-hidden>
          {[0, 150, 300].map((d) => (
            <span key={d} className="h-1.5 w-1.5 animate-bounce rounded-full bg-[#9AA3B2]" style={{ animationDelay: `${d}ms` }} />
          ))}
        </span>
        {label}
      </div>
    </div>
  );
}

export function MaterialChat({ messages, pendingOptions, usingLabel, busy, thinking, onSend, onEditSpace }: Props) {
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const box = useRef<HTMLTextAreaElement>(null);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: 'nearest' }); // effects must not return a value
  }, [messages.length, thinking]);

  const send = (message: string) => {
    if (busy || (!message.trim() && !file)) return;
    onSend(message.trim(), file);
    setText('');
    setFile(null);
    if (box.current) box.current.style.height = '';
  };

  const grow = (el: HTMLTextAreaElement) => {
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  };

  const lastIsQuestion = messages.length > 0 && messages[messages.length - 1].role === 'assistant';

  return (
    <section aria-label="Ask about the materials" className="flex flex-col rounded-2xl border border-white/10 bg-white/[0.015]">
      <header className="flex items-center justify-between gap-2 border-b border-white/10 px-4 py-2.5">
        <h2 className="text-sm font-medium text-white">Ask a follow-up</h2>
        {usingLabel && (
          <span className="flex min-w-0 items-center gap-1.5 rounded-full bg-white/[0.05] px-2.5 py-0.5 text-[11px] text-[#D5DAE1]">
            <span className="truncate">Using: {usingLabel}</span>
            {onEditSpace && (
              <button type="button" onClick={onEditSpace} className="shrink-0 text-[#C5A77B] hover:underline">
                Edit
              </button>
            )}
          </span>
        )}
      </header>

      <div className="max-h-[28rem] min-h-[8rem] space-y-4 overflow-y-auto px-4 py-4" aria-live="polite">
        {messages.length === 0 && !thinking && (
          <div className="space-y-2">
            <p className="text-sm text-[#9AA3B2]">Ask about a material, a room size, one of your projects, or attach a floor plan.</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send(s)}
                  className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-[#D5DAE1] hover:border-[#C5A77B]/60 hover:bg-white/[0.03]"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) =>
          m.role === 'user' ? (
            <div key={i} className="flex justify-end">
              <p className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-[#2A2F38] px-4 py-2 text-sm text-white">
                {m.text}
              </p>
            </div>
          ) : (
            <div key={i} className="flex items-start gap-3">
              <Avatar />
              <div
                className={`max-w-[85%] pt-1 text-sm leading-relaxed ${
                  m.status === 'failed' ? 'text-[#F2A0A2]' : m.status === 'not_found' ? 'text-[#F1C76B]' : 'text-[#D5DAE1]'
                }`}
              >
                <RichText text={m.text} />
              </div>
            </div>
          ),
        )}

        {pendingOptions.length > 0 && lastIsQuestion && !thinking && (
          <div className="flex flex-wrap gap-2 pl-10" aria-label="Quick answers">
            {pendingOptions.map((o) => (
              <button
                key={o}
                type="button"
                disabled={busy}
                onClick={() => send(o)}
                className="rounded-full border border-[#C5A77B]/50 px-3 py-1 text-xs text-white hover:bg-[#C5A77B]/15 disabled:opacity-50"
              >
                {o}
              </button>
            ))}
          </div>
        )}

        {thinking && <Typing label={thinking} />}
        <div ref={end} />
      </div>

      <form
        className="p-3 pt-0"
        onSubmit={(e) => {
          e.preventDefault();
          send(text);
        }}
      >
        <input
          ref={fileInput}
          type="file"
          accept={PLAN_ACCEPT}
          className="hidden"
          data-testid="plan-input"
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            e.target.value = '';
          }}
        />
        <div className="rounded-2xl border border-white/10 bg-[#15181D] focus-within:border-[#C5A77B]/60">
          {file && (
            <div className="px-3 pt-2.5">
              <span className="inline-flex items-center gap-2 rounded-lg bg-white/[0.06] px-2.5 py-1 text-xs text-[#D5DAE1]">
                📄 {file.name}
                <button type="button" aria-label="Remove plan" onClick={() => setFile(null)} className="text-[#9AA3B2] hover:text-white">
                  ✕
                </button>
              </span>
            </div>
          )}
          <div className="flex items-end gap-1 p-1.5">
            <button
              type="button"
              aria-label="Attach floor plan"
              title="Attach a floor plan (PDF, PNG, JPG)"
              onClick={() => fileInput.current?.click()}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-lg text-[#9AA3B2] hover:bg-white/[0.06] hover:text-white"
            >
              +
            </button>
            <textarea
              ref={box}
              rows={1}
              value={text}
              maxLength={2000}
              aria-label="Message"
              placeholder="Ask anything about these materials…"
              onChange={(e) => {
                setText(e.target.value);
                grow(e.target);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  send(text);
                }
              }}
              className="max-h-36 flex-1 resize-none bg-transparent px-1 py-2 text-sm text-white placeholder:text-[#5C6370] focus:outline-none"
            />
            <button
              type="submit"
              aria-label="Send"
              disabled={busy || (!text.trim() && !file)}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#C5A77B] text-black transition-opacity disabled:opacity-30"
            >
              <IconSend className="h-4 w-4" />
            </button>
          </div>
        </div>
        <p className="mt-1.5 text-center text-[10px] text-[#5C6370]">Enter to send · Shift + Enter for a new line · + to attach a floor plan</p>
      </form>
    </section>
  );
}
