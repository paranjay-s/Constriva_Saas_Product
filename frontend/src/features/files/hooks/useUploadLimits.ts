/**
 * The plan upload limits to show and pre-check against: the defaults at first, then the
 * server's own values. Shared by the 2D-to-3D import and the BOQ upload.
 */
import { useEffect, useState } from 'react';
import { DEFAULT_UPLOAD_LIMITS, filesApi, type UploadLimits } from '../api';

export function useUploadLimits(): UploadLimits {
  const [limits, setLimits] = useState<UploadLimits>(DEFAULT_UPLOAD_LIMITS);

  useEffect(() => {
    let current = true;
    void filesApi.getUploadLimits().then((fetched) => {
      if (current) setLimits(fetched);
    });
    return () => {
      current = false;
    };
  }, []);

  return limits;
}
