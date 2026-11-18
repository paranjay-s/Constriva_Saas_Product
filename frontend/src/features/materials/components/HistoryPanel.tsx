/**
 * Chat history: the user's earlier analyses (newest first), like the sidebar of a chat
 * app. Opening one restores its materials, quantities and the whole conversation.
 */
import { useEffect } from 'react';
import { TrashIcon } from '../../../components/ui/Icons';
import type { SessionSummary } from '../schemas';

interface Props {
  open: boolean;
  items: SessionSummary[];
  loading: boolean;
  error: string | null;
  activeId: string | null;
  onClose: () => void;
  onOpen: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onRetry: () => void;
}

function cap(s: string): string {
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}

/** "Today", "Yesterday", "Previous 7 days", or the month. */
function groupOf(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 'Earlier';
  const days = Math.floor((new Date().setHours(0, 0, 0, 0) - new Date(d).setHours(0, 0, 0, 0)) / 86_400_000);
  if (days <= 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7) return 'Previous 7 days';
  return d.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
}

export function HistoryPanel({ open, items, loading, error, activeId, onClose, onOpen, onNew, onDelete, onRetry }: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  const groups: [string, SessionSummary[]][] = [];
  for (const it of items) {
    const g = groupOf(it.created_at);
    const last = groups[groups.length - 1];
    if (last && last[0] === g) last[1].push(it);
    else groups.push([g, [it]]);
  }

  return (
    <div className="fixed inset-0 z-40 flex">
      <aside
        aria-label="Analysis history"
        className="flex h-full w-[300px] max-w-[85vw] flex-col border-r border-white/10 bg-[#111317] shadow-2xl"
      >
        <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
          <h2 className="text-sm font-semibold">History</h2>
          <button type="button" onClick={onClose} aria-label="Close history" className="cursor-pointer text-white/60 hover:text-white">
            ✕
          </button>
        </div>
        <div className="p-3">
          <button
            type="button"
            onClick={onNew}
            className="w-full cursor-pointer rounded-lg border border-white/15 px-3 py-2 text-left text-sm hover:border-[#C5A77B]"
          >
            + New analysis
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-4">
          {loading && items.length === 0 && <p className="px-2 text-sm text-[#7D8594]">Loading…</p>}
          {error && (
            <p role="alert" className="px-2 text-sm text-[#F2A0A2]">
              {error}{' '}
              <button type="button" onClick={onRetry} className="cursor-pointer underline">
                Try again
              </button>
            </p>
          )}
          {!loading && !error && items.length === 0 && (
            <p className="px-2 text-sm text-[#7D8594]">Your analyses will appear here.</p>
          )}
          {groups.map(([label, list]) => (
            <div key={label} className="mt-3">
              <p className="px-2 pb-1 text-[11px] font-medium uppercase tracking-wider text-[#5C6370]">{label}</p>
              <ul className="space-y-0.5">
                {list.map((it) => (
                  <li key={it.id} className="group relative">
                    <button
                      type="button"
                      onClick={() => onOpen(it.id)}
                      className={`w-full cursor-pointer rounded-lg px-2.5 py-2 pr-8 text-left hover:bg-white/[0.06] ${
                        it.id === activeId ? 'bg-white/[0.08]' : ''
                      }`}
                    >
                      <span className="block truncate text-sm text-white/90">{cap(it.scene) || 'Material analysis'}</span>
                      {it.title && <span className="block truncate text-[11px] text-[#7D8594]">{it.title}</span>}
                    </button>
                    <button
                      type="button"
                      aria-label={`Delete ${it.scene || 'analysis'}`}
                      onClick={() => {
                        if (window.confirm('Delete this analysis and its chat?')) onDelete(it.id);
                      }}
                      className="absolute right-1.5 top-1/2 -translate-y-1/2 cursor-pointer p-1 text-white/30 opacity-0 hover:text-[#F2A0A2] focus:opacity-100 group-hover:opacity-100"
                    >
                      <TrashIcon size={14} />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </aside>
      <button type="button" aria-label="Close history" onClick={onClose} className="flex-1 cursor-default bg-black/50" />
    </div>
  );
}
