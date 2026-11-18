/** PDF / Excel download of the whole bill, with a busy state and an error to show inline. */
import { useCallback, useState } from 'react';
import { EXPORT_LABELS, boqApi, boqErrorText } from '../boqApi';
import type { BoqExportFormat, BoqResult } from '../boqSchemas';

export function useBoqExport(result: BoqResult | null, sourceName: string | null) {
  const [busy, setBusy] = useState<BoqExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);

  const download = useCallback(
    async (format: BoqExportFormat) => {
      if (!result) return;
      setBusy(format);
      setError(null);
      try {
        // always the full result: the table's search and filters never change what is exported
        await boqApi.download(format, result, sourceName);
      } catch (e) {
        setError(`${EXPORT_LABELS[format]} download failed. ${boqErrorText(e)}`);
      } finally {
        setBusy(null);
      }
    },
    [result, sourceName],
  );

  return { busy, error, download };
}
