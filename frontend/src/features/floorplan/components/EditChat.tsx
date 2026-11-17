/**
 * Step 4: change the plan in words (typed or spoken). Each reply says what changed, or
 * why it could not, with alternatives. History comes from the server (kept per plan).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { SendIcon as IconSend } from '../../../components/ui/Icons';
import { useSpeechInput } from '../hooks/useSpeechInput';
import type { ChatMessage } from '../schemas';
import { MicButton } from './MicButton';

const SUGGESTIONS = [
  'Make the master bedroom bigger',
  'Add a window to the living room',
  'Swap bedroom 2 and the kitchen',
  'Add a store room next to the kitchen',
];

const STATUS_TONE: Record<string, string> = {
  ok: 'border-[#2E7D4F]/50',
  impossible: 'border-[#E5484D]/50',
  failed: 'border-[#E5484D]/50',
  needs_clarification: 'border-[#F2C46D]/50',
  no_change: 'border-[#3A404B]',
};

interface Props {
  messages: ChatMessage[];
  busy: boolean;
  error: string | null;
  onSend: (text: string) => void;
}

export function EditChat({ messages, busy, error, onSend }: Props) {
  const [text, setText] = useState('');
  const end = useRef<HTMLDivElement>(null);
  const append = useCallback((t: string) => setText((cur) => (cur ? `${cur.trimEnd()} ${t}` : t)), []);
  const speech = useSpeechInput(append);

  useEffect(() => {
    end.current?.scrollIntoView({ block: 'nearest' });
  }, [messages.length, busy]);

  const send = (t: string) => {
    const msg = t.trim();
    if (!msg || busy) return;
    speech.stop();
    onSend(msg);
    setText('');
  };

  return (
    <section aria-label="Change the plan" className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
        {messages.length === 0 && (
          <p className="text-sm text-[#7D8594]">Ask for changes in your own words. Other rooms move only when needed.</p>
        )}
        {messages.map((m, i) =>
          m.role === 'user' ? (
            <div key={i} className="ml-8 rounded-lg bg-[#C5A77B]/15 px-3 py-2 text-sm text-[#F0E3CC]">
              {m.text}
            </div>
          ) : (
            <div
              key={i}
              className={`mr-8 rounded-lg border bg-[#0F1115] px-3 py-2 text-sm text-[#D5DAE1] ${STATUS_TONE[m.status ?? ''] ?? 'border-[#23272F]'}`}
            >
              {m.text}
              {m.version != null && m.status === 'ok' && <span className="ml-2 text-[11px] text-[#7D8594]">v{m.version}</span>}
            </div>
          ),
        )}
        {busy && <div className="mr-8 animate-pulse rounded-lg bg-[#0F1115] px-3 py-2 text-sm text-[#7D8594]">Working on it…</div>}
        {error && <div className="rounded-lg bg-[#E5484D]/10 px-3 py-2 text-sm text-[#FFB4AB]">{error}</div>}
        <div ref={end} />
      </div>

      {messages.length === 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              disabled={busy}
              onClick={() => send(s)}
              className="cursor-pointer rounded-full border border-[#2A2F38] px-2.5 py-1 text-[11px] text-[#9AA3B2] hover:border-[#C5A77B] hover:text-white disabled:opacity-50"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {speech.listening && <p className="mt-2 text-xs text-[#FF8A8D]">Listening… {speech.interim}</p>}
      {speech.error && <p className="mt-2 text-xs text-[#FFB4AB]">{speech.error}</p>}
      <form
        className="mt-3 flex items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          send(text);
        }}
      >
        <textarea
          rows={2}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              send(text);
            }
          }}
          aria-label="Change request"
          placeholder="e.g. make the kitchen 2 feet wider"
          className="min-h-[44px] flex-1 resize-none rounded-md border border-[#2A2F38] bg-[#0F1115] px-3 py-2 text-sm text-white placeholder:text-[#5C6370] focus:border-[#C5A77B] focus:outline-none"
        />
        <MicButton speech={speech} label="Say the change" />
        <button
          type="submit"
          disabled={busy || !text.trim()}
          aria-label="Send"
          className="flex h-9 w-9 shrink-0 cursor-pointer items-center justify-center rounded-full bg-[#C5A77B] text-[#101010] disabled:cursor-not-allowed disabled:opacity-40"
        >
          <IconSend className="h-4 w-4" />
        </button>
      </form>
    </section>
  );
}
