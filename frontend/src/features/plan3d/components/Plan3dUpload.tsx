/** Pick or drop the floor-plan PDF. Same look, checks and limits text as the BOQ upload. */
import { useRef, useState } from 'react';
import { Button } from '../../../components/ui/Button';
import { FilePdfIcon, TrashIcon, UploadIcon } from '../../../components/ui/Icons';
import type { UploadLimits } from '../../files';
import { fileSizeText } from '../plan3dLogic';

interface Plan3dUploadProps {
  file: File | null;
  /** The server's upload limits, shown under the dropzone. */
  limits: UploadLimits;
  /** A plan is being sent: the file cannot be changed now. */
  disabled: boolean;
  /** Called with whatever was picked or dropped; the page validates it. */
  onPick: (file: File) => void;
  onClear: () => void;
}

const FOCUS = 'focus:outline-none focus-visible:ring-2 focus-visible:ring-[#7ce8f2]';

export function Plan3dUpload({ file, limits, disabled, onPick, onClear }: Plan3dUploadProps) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const browse = () => input.current?.click();

  return (
    <div className="flex flex-col gap-6">
      <input
        ref={input}
        type="file"
        accept="application/pdf,.pdf"
        className="hidden"
        aria-label="Floor plan PDF"
        disabled={disabled}
        onChange={(e) => {
          const picked = e.target.files?.[0];
          if (picked) onPick(picked);
          e.target.value = ''; // picking the same file again must fire a change
        }}
      />

      {!file ? (
        <button
          type="button"
          disabled={disabled}
          onClick={browse}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const dropped = e.dataTransfer.files?.[0];
            if (dropped && !disabled) onPick(dropped);
          }}
          className={`flex w-full cursor-pointer flex-col items-center justify-center rounded-[22px] border-2 border-dashed p-6 text-center transition-all disabled:cursor-not-allowed disabled:opacity-50 sm:p-10 ${FOCUS} ${
            dragging
              ? 'border-[#7ce8f2] bg-[#121a26]'
              : 'border-[#243041] bg-[#0b1019] hover:border-[#3a4658] hover:bg-[#0e141e]'
          }`}
        >
          <span className="mb-4 flex h-14 w-14 items-center justify-center rounded-full border border-[#243041] bg-[#121a26] text-[#7ce8f2]">
            <UploadIcon size={26} aria-hidden="true" />
          </span>
          <span className="text-[17px] font-medium text-white">Drag and drop your floor plan PDF here</span>
          <span className="mt-1.5 max-w-sm text-xs text-[#a3afbf]">
            Or click to browse your files. Single or multi-page architectural floor plans accepted.
          </span>
          <span className="mt-4 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 font-mono text-[11px] uppercase tracking-wider text-[#8b97a8]">
            <span>Format: PDF</span>
            <span aria-hidden="true">•</span>
            <span>Max Size: {limits.max_pdf_mb} MB</span>
            <span aria-hidden="true">•</span>
            <span>Up to {limits.max_pdf_pages} pages</span>
          </span>
        </button>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#243041] bg-[#0b1019] p-4 sm:p-5">
          <div className="flex min-w-0 items-center gap-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[#243041] bg-[#121a26] text-[#7ce8f2]">
              <FilePdfIcon size={20} aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-white">{file.name}</div>
              <div className="font-mono text-xs text-[#8b97a8]">{fileSizeText(file.size)} • Ready to upload</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={browse} disabled={disabled}>
              Replace
            </Button>
            <button
              type="button"
              onClick={onClear}
              disabled={disabled}
              aria-label="Remove file"
              title="Remove file"
              className={`cursor-pointer rounded-xl p-2 text-[#8b97a8] transition-colors hover:text-[#FFB4AB] disabled:cursor-not-allowed disabled:opacity-50 ${FOCUS}`}
            >
              <TrashIcon size={16} aria-hidden="true" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
