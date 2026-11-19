/**
 * Furniture models (/3d/furniture): the 3D builder's own page that lists the furniture it
 * places in a house, where a model can be replaced with the person's own .glb file. It is
 * shown in an iframe and needs no job.
 */
import { Button } from '../../components/ui/Button';
import { BackLink, ErrorNotice, PageFrame, PageTitle, StatusNote } from './components/Plan3dParts';
import { useEmbedAccess } from './hooks/useEmbedAccess';
import { embedUrl } from './plan3dApi';

export function Plan3dFurniturePage() {
  const embed = useEmbedAccess(null);

  return (
    <PageFrame wide>
      <div className="flex flex-col items-start gap-6">
        <BackLink to="/3d">All plans</BackLink>
        <PageTitle eyebrow="2D to 3D" title="Furniture models">
          The furniture the 3D builder places in a house. You can replace a model with your own .glb file.
        </PageTitle>
      </div>

      {embed.loading && <StatusNote>Opening the furniture models…</StatusNote>}
      {embed.error && (
        <ErrorNotice message={`The furniture models could not be opened. ${embed.error}`}>
          <Button variant="secondary" size="sm" onClick={embed.reload}>
            Retry
          </Button>
        </ErrorNotice>
      )}
      {embed.access && (
        <div className="h-[75vh] min-h-[420px] overflow-hidden rounded-[22px] border border-[#243041] bg-[#0b1019]">
          <iframe title="Furniture models" src={embedUrl(embed.access.furniture_url)} className="h-full w-full border-0" />
        </div>
      )}
    </PageFrame>
  );
}
