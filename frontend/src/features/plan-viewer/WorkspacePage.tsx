/**
 * Route /projects/3d-workspace: the live 3D model of the active project with its bill of
 * materials. The plan comes from GET /plans/project/{id}; the quantities from the sheets API.
 */
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useProject } from '../../context/ProjectContext';
import { ArrowLeft, Refresh } from '../dashboard';
import { filesApi } from '../files';
import { sheetsApi, type SheetItem } from '../sheets';
import { PlanViewer, getMaterialHighlightStyle } from './PlanViewer';

type Tab = 'all' | 'structure' | 'walls' | 'flooring';
type PlanState = 'loading' | 'loaded' | 'none';

const TABS: { id: Tab; label: string }[] = [
  { id: 'all', label: 'All items' },
  { id: 'structure', label: 'Structure & RCC' },
  { id: 'walls', label: 'Masonry & plaster' },
  { id: 'flooring', label: 'Tiles & flooring' },
];

const has = (text: string, ...words: string[]) => words.some((w) => text.includes(w));

function inTab(item: SheetItem, tab: Tab): boolean {
  if (tab === 'all') return true;
  const cat = (item.category || '').toLowerCase();
  const tag = (item.surface_tag || '').toLowerCase();
  const name = (item.name || '').toLowerCase();
  if (tab === 'structure') {
    return (
      has(cat, 'structural', 'masonry', 'aggregate', 'binder') ||
      has(tag, 'reinforcement', 'aggregate', 'concrete') ||
      has(name, 'steel', 'ballast', 'sand', 'cement')
    );
  }
  if (tab === 'walls') return has(cat, 'masonry', 'plaster') || has(tag, 'masonry', 'plaster') || has(name, 'brick', 'plaster');
  return has(cat, 'flooring', 'tiling') || has(tag, 'tile') || has(name, 'tile');
}

/** "metric_tons" -> "metric tons" */
const unitLabel = (unit: string) => (unit || '').replace(/_/g, ' ');

const qty = (n: number) => Number(n || 0).toLocaleString('en-IN', { maximumFractionDigits: 1 });

function areaOf(item: SheetItem): string {
  if (item.area) return `${item.area.toFixed(1)} m²`;
  if (item.secondary_quantity) return `${item.secondary_quantity} ${item.secondary_unit || ''}`.trim();
  return '–';
}

export function WorkspacePage() {
  const { activeProject, setPlanData, selectedMaterialTag, setSelectedMaterialTag } = useProject();

  const [tab, setTab] = useState<Tab>('all');
  const [done, setDone] = useState<'csv' | 'pdf' | null>(null);
  const [plan, setPlan] = useState<PlanState>('loading');

  const [items, setItems] = useState<SheetItem[]>([]);
  const [stale, setStale] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isRecalculating, setIsRecalculating] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const projectId = activeProject?.id;

  useEffect(() => {
    if (!projectId) return;
    let current = true;

    setPlan('loading');
    filesApi
      .getProjectPlan(projectId)
      .then((res) => {
        if (!current) return;
        if (res && res.plan_json) {
          setPlanData(res.plan_json);
          setPlan('loaded');
        } else {
          setPlan('none');
        }
      })
      .catch((err) => {
        console.warn('Plan could not be loaded:', err);
        if (current) setPlan('none');
      });

    setIsLoading(true);
    setErrorMsg(null);
    setItems([]);
    sheetsApi
      .getSheet(projectId)
      .then(async (res) => {
        if (!current) return;
        if (res && Array.isArray(res.items) && res.items.length > 0) {
          setItems(res.items);
          setStale(Boolean(res.stale));
          return;
        }
        // an empty or new sheet: work the quantities out from the saved plan
        try {
          const again = await sheetsApi.recalculateFromPlan(projectId);
          if (current && again && Array.isArray(again.items)) {
            setItems(again.items);
            setStale(Boolean(again.stale));
          }
        } catch (err) {
          console.warn('First calculation failed:', err);
        }
      })
      .catch((err) => {
        if (!current) return;
        console.warn('Sheet could not be loaded:', err);
        setErrorMsg('The bill of materials could not be loaded. Check the connection and try again.');
      })
      .finally(() => {
        if (current) setIsLoading(false);
      });

    return () => {
      current = false;
    };
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const recalculate = async () => {
    if (!projectId) return;
    setIsRecalculating(true);
    setErrorMsg(null);
    try {
      const res = await sheetsApi.recalculateFromPlan(projectId);
      if (res && Array.isArray(res.items)) {
        setItems(res.items);
        setStale(Boolean(res.stale));
      }
    } catch (err) {
      setErrorMsg(err instanceof Error && err.message ? err.message : 'Recalculation failed. Please try again.');
    } finally {
      setIsRecalculating(false);
    }
  };

  const shown = useMemo(() => items.filter((i) => inTab(i, tab)), [items, tab]);

  const flash = (kind: 'csv' | 'pdf') => {
    setDone(kind);
    window.setTimeout(() => setDone(null), 3000);
  };

  const exportFile = async (kind: 'csv' | 'pdf') => {
    if (!projectId) return;
    const name = activeProject?.name || 'project';
    try {
      if (kind === 'csv') await sheetsApi.downloadCsv(projectId, name);
      else await sheetsApi.downloadPdf(projectId, name);
      flash(kind);
    } catch (err) {
      if (kind === 'csv' && items.length > 0) {
        // the server export failed: save the rows already on screen instead
        saveCsv(items, name);
        flash(kind);
        return;
      }
      setErrorMsg(err instanceof Error && err.message ? err.message : 'The export failed. Please try again.');
    }
  };

  const status = isLoading
    ? 'Loading'
    : errorMsg && items.length === 0
      ? 'Not loaded'
      : items.length === 0
        ? 'No quantities yet'
        : stale
          ? 'Out of date'
          : 'Synchronized';

  if (!activeProject) {
    return (
      <main className="cv-main">
        <section className="cv-col" style={{ flex: '1 1 320px', maxWidth: 520 }}>
          <div className="cv-title cv-rise">
            <h1>3D workspace</h1>
            <p className="cv-sub">no project selected</p>
          </div>
          <div className="cv-card cv-rise" style={{ ['--d' as string]: '.15s' }}>
            <p>Choose a project on the overview to see its 3D model and bill of materials.</p>
            <Link to="/home" className="cv-btn cv-btn-primary" style={{ marginTop: 14 }}>
              Go to overview
            </Link>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="cv-main cv-ws">
      <section className="cv-ws-stage" aria-label="3D model">
        <div className="cv-ws-view cv-fade">
          <PlanViewer transparent />
        </div>
        <div className="cv-ws-fade" aria-hidden="true" />

        <div className="cv-ws-side">
          <div className="cv-title cv-rise">
            <h1>3D workspace</h1>
            <div className="cv-ws-meta">
              <span data-testid="workspace-project">{activeProject.name}</span>
              <span className="cv-badge">{activeProject.type}</span>
              {plan === 'loaded' && (
                <span className="cv-badge is-live">
                  <span className="cv-dot cv-pulse" style={{ width: 6, height: 6 }} aria-hidden="true" />
                  3D active
                </span>
              )}
              {plan === 'none' && <span className="cv-badge is-quiet">No saved plan</span>}
            </div>
          </div>

          <Link to="/projects/options" className="cv-btn cv-btn-sm cv-rise" style={{ ['--d' as string]: '.15s', background: 'rgba(14,20,30,.84)' }}>
            <ArrowLeft />
            Options
          </Link>

          <div className="cv-card cv-card-glow cv-push cv-rise" style={{ ['--d' as string]: '.35s' }}>
            <div className="cv-between" style={{ flexWrap: 'wrap' }}>
              <h2 className="cv-h2">Engineering quantity survey</h2>
              <span className="cv-tag" style={{ border: '1px solid rgba(124,232,242,.25)', fontSize: 11 }}>
                CPWD / IS 456
              </span>
            </div>
            <div className="cv-between" style={{ alignItems: 'flex-end', marginTop: 16 }}>
              <span style={{ fontSize: 14, color: 'var(--cv-text-2)' }}>Total verified materials</span>
              <span className="cv-big" data-testid="material-count">
                {isLoading ? '–' : items.length}
              </span>
            </div>
            <div className="cv-between" style={{ marginTop: 14, fontSize: 14 }}>
              <span style={{ color: 'var(--cv-muted)' }}>Survey status</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, color: status === 'Synchronized' ? 'var(--cv-ac-hi)' : 'var(--cv-text-2)' }} data-testid="survey-status">
                {status === 'Synchronized' && <span className="cv-dot cv-pulse" aria-hidden="true" />}
                {status}
              </span>
            </div>
            <button type="button" className="cv-btn cv-btn-block" style={{ marginTop: 18 }} disabled={isRecalculating} onClick={() => void recalculate()}>
              <Refresh className={isRecalculating ? 'cv-spin' : undefined} style={{ color: 'var(--cv-ac)' }} />
              {isRecalculating ? 'Recalculating…' : 'Recalculate quantities'}
            </button>
          </div>
        </div>
      </section>

      <section className="cv-card cv-ws-bom cv-rise" style={{ ['--d' as string]: '.25s' }} aria-label="Bill of materials">
        <div className="cv-between" style={{ flexWrap: 'wrap' }}>
          <h2 className="cv-h2">
            Bill of materials{' '}
            <span className="cv-note" style={{ fontWeight: 400 }}>
              {plural(shown.length)}
            </span>
          </h2>
          <div style={{ display: 'flex', gap: 8 }}>
            <button type="button" className="cv-btn cv-btn-sm" disabled={items.length === 0} onClick={() => void exportFile('csv')}>
              {done === 'csv' ? 'CSV downloaded' : 'Export CSV'}
            </button>
            <button type="button" className="cv-btn cv-btn-sm" disabled={items.length === 0} onClick={() => void exportFile('pdf')}>
              {done === 'pdf' ? 'PDF downloaded' : 'Printable PDF'}
            </button>
          </div>
        </div>

        <div className="cv-tabs" role="group" aria-label="Material category">
          {TABS.map((t) => (
            <button key={t.id} type="button" aria-pressed={tab === t.id} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </div>

        {errorMsg && (
          <div className="cv-error cv-between" role="alert" style={{ marginTop: 10 }}>
            <span>{errorMsg}</span>
            <button type="button" className="cv-link" style={{ minHeight: 0, color: 'inherit', textDecoration: 'underline' }} onClick={() => void recalculate()}>
              Retry
            </button>
          </div>
        )}

        <div className="cv-table-wrap">
          {isLoading && items.length === 0 ? (
            <p className="cv-state">Loading the quantities…</p>
          ) : shown.length === 0 ? (
            <div className="cv-state">
              <p>{items.length === 0 ? 'No quantities yet for this project.' : 'No items in this category.'}</p>
              {items.length === 0 && (
                <button type="button" className="cv-btn cv-btn-sm" style={{ marginTop: 12 }} disabled={isRecalculating} onClick={() => void recalculate()}>
                  Recalculate quantities
                </button>
              )}
            </div>
          ) : (
            <table className="cv-table">
              <thead>
                <tr>
                  <th scope="col">Material &amp; category</th>
                  <th scope="col">Surface / area</th>
                  <th scope="col" className="is-num">
                    Total verified qty
                  </th>
                </tr>
              </thead>
              <tbody>
                {shown.map((item) => {
                  const tag = item.surface_tag || item.name;
                  const selected = selectedMaterialTag === tag;
                  const waste = Math.round((item.waste_factor || 0) * 100);
                  return (
                    <tr key={item.id} data-selected={selected} data-testid="bom-row" onClick={() => setSelectedMaterialTag(selected ? null : tag)}>
                      <td>
                        <button type="button" className="cv-mat" aria-pressed={selected} aria-label={`Highlight ${item.name} in the 3D view`}>
                          <i style={{ background: getMaterialHighlightStyle(tag).color }} aria-hidden="true" />
                          <span>
                            {item.name}
                            <small>
                              {item.category}
                              {waste > 0 ? ` · ${waste}% waste` : ''}
                            </small>
                          </span>
                        </button>
                      </td>
                      <td style={{ color: 'var(--cv-text-2)' }}>
                        {areaOf(item)}
                        {item.surface_tag && <small>{item.surface_tag.replace(/_/g, ' ')}</small>}
                      </td>
                      <td className="is-num">
                        <span className="cv-qty">
                          {qty(item.total_quantity || item.quantity)} <span>{unitLabel(item.unit)}</span>
                        </span>
                        {item.quantity > 0 && item.quantity !== item.total_quantity && <small>base {qty(item.quantity)}</small>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        <div className="cv-between" style={{ marginTop: 12 }}>
          <p style={{ fontSize: 13, color: '#c0cad7' }}>Click any material to glow its surfaces in the 3D view.</p>
          {selectedMaterialTag && (
            <button type="button" className="cv-link" style={{ flex: 'none', fontSize: 13 }} onClick={() => setSelectedMaterialTag(null)}>
              Clear highlight
            </button>
          )}
        </div>
      </section>
    </main>
  );
}

const plural = (n: number) => `${n} ${n === 1 ? 'item' : 'items'}`;

function saveCsv(items: SheetItem[], projectName: string): void {
  const cell = (v: unknown) => `"${String(v ?? '-').replace(/"/g, '""')}"`;
  const rows = items.map((m, i) =>
    [i + 1, m.name, m.category, m.surface_tag || '-', m.quantity, m.unit, `${Math.round((m.waste_factor || 0) * 100)}%`, m.total_quantity, m.area || '-']
      .map(cell)
      .join(','),
  );
  const csv = ['Item #,Material,Category,Surface tag,Base qty,Unit,Waste %,Total qty,Area (m2)', ...rows].join('\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = `${projectName}_BOQ_Quantities.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export default WorkspacePage;
