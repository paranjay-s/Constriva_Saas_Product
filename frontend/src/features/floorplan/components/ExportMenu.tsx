/** Downloads: every file is made from the same plan on the server. PDF, PNG and SVG follow
 * the active view (engineering or presentation); DXF, DWG and IFC are always engineering. */
import { useState } from 'react';
import { IconDownload } from '../../../components/ui/Icons';
import { floorplanApi } from '../api';
import { EXPORT_FORMATS, VIEW_FORMATS, type ExportFormat, type PlanView } from '../schemas';

export function ExportMenu({ planId, view = 'engineering' }: { planId: string; view?: PlanView }) {
  const [busy, setBusy] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);

  const get = async (fmt: ExportFormat) => {
    setBusy(fmt);
    setError(null);
    try {
      await floorplanApi.download(planId, fmt, 200, view);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Download failed');
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {EXPORT_FORMATS.map((f) => (
        <button
          key={f.value}
          type="button"
          title={
            view === 'presentation'
              ? `${f.label}${VIEW_FORMATS.includes(f.value) ? ', presentation plan' : ', engineering drawing'}`
              : f.label
          }
          disabled={busy !== null}
          onClick={() => void get(f.value)}
          className="inline-flex cursor-pointer items-center gap-1 rounded-md border border-[#2A2F38] bg-[#16181E] px-2.5 py-1.5 text-xs text-[#D5DAE1] hover:border-[#C5A77B] disabled:opacity-50"
        >
          <IconDownload className="h-3.5 w-3.5" />
          {busy === f.value ? '…' : f.value.toUpperCase()}
        </button>
      ))}
      {error && <span className="text-xs text-[#FFB4AB]">{error}</span>}
    </div>
  );
}
