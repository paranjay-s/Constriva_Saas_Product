/**
 * Builds that finished or failed while the person was away (the server keeps them), with a link
 * to each, and the switch for the emails about them.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { plan3dApi, plan3dErrorText } from "../plan3dApi";
import type { Plan3dNotifications } from "../plan3dSchemas";

const SHOWN = 5;

export function Plan3dNotices() {
  const [data, setData] = useState<Plan3dNotifications | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    plan3dApi.notifications(controller.signal).then(
      (d) => {
        if (!controller.signal.aborted) setData(d);
      },
      () => {
        // no notices to show: the rest of the page works without them
      },
    );
    return () => controller.abort();
  }, []);

  if (!data) return null;

  const toggle = (email: boolean) => {
    setSaving(true);
    setError(null);
    plan3dApi
      .setEmail(email)
      .then(
        (on) => setData((d) => (d ? { ...d, email: on } : d)),
        (e: unknown) => setError(plan3dErrorText(e)),
      )
      .finally(() => setSaving(false));
  };

  return (
    <section aria-label="Build notifications" className="flex flex-col gap-3">
      {data.items.length > 0 && (
        <ul className="flex flex-col gap-2">
          {data.items.slice(0, SHOWN).map((n) => (
            <li
              key={`${n.job_id}-${n.at}`}
              className="flex flex-wrap items-center gap-2 text-sm"
            >
              <span aria-hidden="true">{n.outcome === "done" ? "✓" : "!"}</span>
              <Link to={`/3d/${n.job_id}`} className="underline">
                {n.title}
              </Link>
              <time dateTime={n.at} className="opacity-70">
                {new Date(n.at).toLocaleString()}
              </time>
            </li>
          ))}
        </ul>
      )}
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={data.email}
          disabled={saving}
          onChange={(e) => toggle(e.target.checked)}
        />
        Email me when a long build finishes
      </label>
      {error && (
        <p role="alert" className="text-sm">
          {error}
        </p>
      )}
    </section>
  );
}
