/**
 * One history for both agents: floor plan chats and material analyses, newest first.
 * Each source loads on its own, so one failing still shows the other.
 */
import { useCallback, useEffect, useState } from 'react';
import { floorplanApi } from '../floorplan/api';
import { materialApi } from '../materials/api';

export type ChatKind = 'plan' | 'analysis';

export interface ChatSummary {
  id: string;
  kind: ChatKind;
  title: string;
  subtitle: string;
  createdAt: string;
  href: string;
}

const cap = (s: string) => (s ? s[0].toUpperCase() + s.slice(1) : s);

export function useChatHistory() {
  const [items, setItems] = useState<ChatSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    const [plans, analyses] = await Promise.allSettled([floorplanApi.list(), materialApi.list()]);
    const out: ChatSummary[] = [];
    if (plans.status === 'fulfilled') {
      for (const p of plans.value) {
        out.push({
          id: p.id,
          kind: 'plan',
          title: p.name,
          subtitle: `2D floor plan · v${p.version}`,
          createdAt: p.created_at,
          href: `/projects/ai-generator?plan=${encodeURIComponent(p.id)}`,
        });
      }
    }
    if (analyses.status === 'fulfilled') {
      for (const a of analyses.value) {
        out.push({
          id: a.id,
          kind: 'analysis',
          title: cap(a.scene) || a.title || 'Material analysis',
          subtitle: a.title || 'Material analysis',
          createdAt: a.created_at,
          href: `/materials/analyse?analysis=${encodeURIComponent(a.id)}`,
        });
      }
    }
    out.sort((x, y) => (y.createdAt || '').localeCompare(x.createdAt || ''));
    setItems(out);
    const failed = [plans, analyses].filter((r) => r.status === 'rejected').length;
    setError(failed === 2 ? 'History could not be loaded.' : null);
    setLoading(false);
  }, []);

  const remove = useCallback(async (item: ChatSummary) => {
    if (item.kind !== 'analysis') return;
    await materialApi.remove(item.id);
    setItems((list) => list.filter((x) => !(x.kind === item.kind && x.id === item.id)));
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { items, loading, error, refresh, remove };
}

/** "Today", "Yesterday", "Previous 7 days", "Previous 30 days", or the month. */
export function dayGroup(iso: string, now = new Date()): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 'Earlier';
  const days = Math.floor((new Date(now).setHours(0, 0, 0, 0) - new Date(d).setHours(0, 0, 0, 0)) / 86_400_000);
  if (days <= 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7) return 'Previous 7 days';
  if (days < 30) return 'Previous 30 days';
  return d.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
}
