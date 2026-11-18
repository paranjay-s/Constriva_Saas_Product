/** Pick or drop the floor-plan PDF, then start. Same look as the plan import dropzone. */
import { useRef, useState } from 'react';
import { Button } from '../../../components/ui/Button';
import { ArrowRightIcon, FilePdfIcon, TrashIcon, UploadIcon } from '../../../components/ui/Icons';
import { formatFileSize } from '../boqLogic';

interface BoqUploadProps {
  file: File | null;
  /** Called with whatever was picked or dropped; the page validates it. */
  onPick: (file: File) => void;
  onClear: () => void;
  onStart: () => void;
  onCancel: () => void;
}

const FOCUS = 'focus:outline-none focus-visible:ring-2 focus-visible:ring-[#C5A77B]';

export function BoqUpload({ file, onPick, onClear, onStart, onCancel }: BoqUploadProps) {
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
        onChange={(e) => {
          const picked = e.target.files?.[0];
          if (picked) onPick(picked);
          e.target.value = ''; // picking the same file again must fire a change
        }}
      />

      {!file ? (
        <button
          type="button"
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
            if (dropped) onPick(dropped);
          }}
          className={`flex w-full cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 text-center transition-all sm:p-10 ${FOCUS} ${
            dragging
              ? 'border-[#C5A77B] bg-[#202020]'
              : 'border-[#303030] bg-[#141414] hover:border-[#444444] hover:bg-[#181818]'
          }`}
        >
          <span className="mb-4 flex h-14 w-14 items-center justify-center rounded-full border border-[#303030] bg-[#202020] text-[#C5A77B]">
            <UploadIcon size={26} aria-hidden="true" />
          </span>
          <span className="font-display text-lg font-semibold text-white">Drag and drop your floor plan PDF here</span>
          <span className="mt-1.5 max-w-sm text-xs text-[#A6A6A6]">
            Or click to browse your files. Single or multi-page architectural floor plans accepted.
          </span>
          <span className="mt-4 flex items-center gap-4 font-mono text-[11px] uppercase tracking-wider text-[#737373]">
            <span>Format: PDF</span>
            <span aria-hidden="true">•</span>
            <span>Max Size: 50 MB</span>
          </span>
        </button>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded border border-[#303030] bg-[#141414] p-4 sm:p-5">
          <div className="flex min-w-0 items-center gap-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded border border-[#303030] bg-[#202020] text-[#C5A77B]">
              <FilePdfIcon size={20} aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-white">{file.name}</div>
              <div className="font-mono text-xs text-[#737373]">{formatFileSize(file.size)} • Ready to process</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={browse}>
              Replace
            </Button>
            <button
              type="button"
              onClick={onClear}
              aria-label="Remove file"
              title="Remove file"
              className={`cursor-pointer rounded p-2 text-[#737373] transition-colors hover:text-[#FFB4AB] ${FOCUS}`}
            >
              <TrashIcon size={16} aria-hidden="true" />
            </button>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between gap-3 border-t border-[#303030] pt-4">
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button variant="primary" size="lg" disabled={!file} onClick={onStart} rightIcon={<ArrowRightIcon size={16} aria-hidden="true" />}>
          Generate BOQ
        </Button>
      </div>
    </div>
  );
}
