/**
 * While the chosen quality is still building, the Low house that was built first, to walk through
 * now. When the build is done the page shows the walkthrough step, whose new iframe loads the
 * finished house: nothing has to be reloaded by hand.
 */
import { useRef } from "react";
import { useEmbedAccess } from "../hooks/useEmbedAccess";
import { embedUrl } from "../plan3dApi";

export function PreviewWalkthrough({ jobId }: { jobId: string }) {
  const frame = useRef<HTMLIFrameElement>(null);
  const embed = useEmbedAccess(jobId, frame);
  const url = embed.access?.walkthrough_url ?? null;
  if (!url) return null;
  return (
    <section aria-label="Preview" className="flex flex-col gap-2">
      <p className="text-sm text-[#c9d3df]">
        A quick Low quality version to walk through while the chosen quality is
        built. It is replaced when the build is done.
      </p>
      <div className="aspect-video w-full overflow-hidden rounded-[22px] border border-[#243041]">
        <iframe
          ref={frame}
          title="3D walkthrough preview"
          src={embedUrl(url)}
          allow="fullscreen"
          className="h-full w-full border-0"
        />
      </div>
    </section>
  );
}
