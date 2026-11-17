/**
 * Route /projects/ai-generator. Renders the new floor plan generator; the old page is
 * kept at /projects/ai-generator/legacy until it is approved for removal.
 */
import { FloorplanPage } from '../floorplan';

export function AiGeneratorPage() {
  return <FloorplanPage />;
}
