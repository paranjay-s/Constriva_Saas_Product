/** 1-4 photos of the same space, with previews. */
import { useEffect, useMemo, useRef } from 'react';
import { IconUpload } from '../../../components/ui/Icons';

export const MAX_IMAGES = 4;
const ACCEPT = 'image/jpeg,image/png,image/webp';

export function UploadPanel({ images, onChange }: { images: File[]; onChange: (files: File[]) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const previews = useMemo(() => images.map((f) => ({ file: f, url: URL.createObjectURL(f) })), [images]);
  useEffect(() => () => previews.forEach((p) => URL.revokeObjectURL(p.url)), [previews]);

  const add = (list: FileList | null) => {
    if (!list) return;
    const picked = Array.from(list).filter((f) => ACCEPT.split(',').includes(f.type));
    onChange([...images, ...picked].slice(0, MAX_IMAGES));
  };

  return (
    <section aria-label="Photos" className="space-y-3">
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        multiple
        className="hidden"
        data-testid="photo-input"
        onChange={(e) => {
          add(e.target.files);
          e.target.value = '';
        }}
      />
      {previews.length === 0 ? (
        <button
          type="button"
          onClick={() => input.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            add(e.dataTransfer.files);
          }}
          className="flex h-56 w-full flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-[#3A404B] bg-white/[0.02] text-sm text-[#9AA3B2] hover:border-[#C5A77B] hover:text-white"
        >
          <IconUpload className="h-6 w-6" />
          <span>Upload a photo of a room, kitchen or facade</span>
          <span className="text-xs text-[#5C6370]">JPG, PNG or WEBP · up to {MAX_IMAGES} photos of the same space</span>
        </button>
      ) : (
        <div className="grid grid-cols-2 gap-2">
          {previews.map((p, i) => (
            <figure key={p.url} className="group relative overflow-hidden rounded-lg border border-white/10 bg-black/40">
              <img src={p.url} alt={`Photo ${i + 1}`} className="h-36 w-full object-cover" />
              <button
                type="button"
                aria-label={`Remove photo ${i + 1}`}
                onClick={() => onChange(images.filter((_, j) => j !== i))}
                className="absolute right-1.5 top-1.5 rounded bg-black/70 px-1.5 text-xs text-white opacity-80 hover:opacity-100"
              >
                ✕
              </button>
            </figure>
          ))}
          {images.length < MAX_IMAGES && (
            <button
              type="button"
              onClick={() => input.current?.click()}
              className="flex h-36 items-center justify-center rounded-lg border border-dashed border-[#3A404B] text-xs text-[#9AA3B2] hover:border-[#C5A77B]"
            >
              + Add photo
            </button>
          )}
        </div>
      )}
    </section>
  );
}
