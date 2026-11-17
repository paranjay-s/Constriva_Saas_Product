/**
 * Step 1: plot, rooms and a free description (typed or spoken). Everything is optional
 * except a plot size somewhere (form or description); the description wins on conflicts.
 */
import { zodResolver } from '@hookform/resolvers/zod';
import { useCallback } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { Button } from '../../../components/ui/Button';
import { IconSparkles } from '../../../components/ui/Icons';
import { useSpeechInput } from '../hooks/useSpeechInput';
import { type BriefFormInput, type BriefFormValues, EMPTY_FORM, EXTRA_ROOMS, POOL_LAYOUTS, SIDES, briefFormSchema } from '../schemas';
import { MicButton } from './MicButton';

const EXAMPLES = [
  '3 BHK on a 30x45 ft plot, road on the east, master bedroom with attached bath, kitchen next to dining',
  '4 bedrooms, all with attached toilets, a courtyard and car parking in front',
  '2 bedroom house with a study and a sit-out, 10 x 15 m plot',
];

const inputCls =
  'w-full rounded-md border border-[#2A2F38] bg-[#0F1115] px-3 py-2 text-sm text-white placeholder:text-[#5C6370] focus:border-[#C5A77B] focus:outline-none';
const labelCls = 'mb-1 block text-xs font-medium text-[#9AA3B2]';

interface Props {
  defaultValues?: BriefFormInput;
  busy: boolean;
  onSubmit: (values: BriefFormValues) => void;
}

export function BriefForm({ defaultValues = EMPTY_FORM, busy, onSubmit }: Props) {
  const {
    register,
    handleSubmit,
    control,
    setValue,
    getValues,
    formState: { errors },
  } = useForm<BriefFormInput, unknown, BriefFormValues>({
    resolver: zodResolver(briefFormSchema),
    defaultValues,
  });

  const appendSpoken = useCallback(
    (text: string) => {
      const cur = getValues('prompt') ?? '';
      setValue('prompt', cur ? `${cur.trimEnd()} ${text}` : text, { shouldValidate: true });
    },
    [getValues, setValue],
  );
  const speech = useSpeechInput(appendSpoken);
  const extras = useWatch({ control, name: 'extras' }) ?? [];
  const unit = useWatch({ control, name: 'unit' });

  const toggleExtra = (value: string) =>
    setValue('extras', extras.includes(value) ? extras.filter((e) => e !== value) : [...extras, value]);

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-5" noValidate>
      <div>
        <div className="mb-1 flex items-center justify-between">
          <label htmlFor="fp-prompt" className={labelCls}>
            Describe the house (type or speak)
          </label>
          <MicButton speech={speech} label="Describe the house" />
        </div>
        <textarea
          id="fp-prompt"
          rows={5}
          {...register('prompt')}
          placeholder={EXAMPLES[0]}
          className={`${inputCls} resize-y leading-relaxed`}
        />
        {speech.listening && (
          <p className="mt-1 text-xs text-[#FF8A8D]" aria-live="polite">
            Listening… {speech.interim}
          </p>
        )}
        {speech.error && <p className="mt-1 text-xs text-[#FFB4AB]">{speech.error}</p>}
        {errors.prompt && <p className="mt-1 text-xs text-[#FFB4AB]">{errors.prompt.message}</p>}
        <div className="mt-2 flex flex-wrap gap-1.5">
          {EXAMPLES.slice(1).map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => setValue('prompt', ex, { shouldValidate: true })}
              className="cursor-pointer rounded-full border border-[#2A2F38] px-2.5 py-1 text-[11px] text-[#9AA3B2] hover:border-[#C5A77B] hover:text-white"
            >
              {ex.length > 48 ? `${ex.slice(0, 48)}…` : ex}
            </button>
          ))}
        </div>
      </div>

      <fieldset className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <legend className={`${labelCls} col-span-full mb-2`}>Plot (leave empty if it is in the description)</legend>
        <div>
          <label htmlFor="fp-width" className={labelCls}>Width ({unit})</label>
          <input id="fp-width" type="number" step="any" min={1} {...register('plot_width')} className={inputCls} />
        </div>
        <div>
          <label htmlFor="fp-depth" className={labelCls}>Depth ({unit})</label>
          <input id="fp-depth" type="number" step="any" min={1} {...register('plot_depth')} className={inputCls} />
        </div>
        <div>
          <label htmlFor="fp-unit" className={labelCls}>Unit</label>
          <select id="fp-unit" {...register('unit')} className={inputCls}>
            <option value="ft">feet</option>
            <option value="m">metres</option>
          </select>
        </div>
        <div>
          <label htmlFor="fp-road" className={labelCls}>Road side</label>
          <select id="fp-road" {...register('road_side')} className={inputCls}>
            <option value="">not set</option>
            {SIDES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        {errors.plot_depth && <p className="col-span-full text-xs text-[#FFB4AB]">{errors.plot_depth.message}</p>}
      </fieldset>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="fp-beds" className={labelCls}>Bedrooms</label>
          <input id="fp-beds" type="number" min={0} max={12} {...register('bedrooms')} className={inputCls} />
        </div>
        <div>
          <label htmlFor="fp-baths" className={labelCls}>Bathrooms</label>
          <input id="fp-baths" type="number" min={0} max={12} {...register('bathrooms')} className={inputCls} />
        </div>
      </div>

      <div>
        <span className={labelCls}>Extra rooms</span>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Extra rooms">
          {EXTRA_ROOMS.map((x) => {
            const on = extras.includes(x.value);
            return (
              <button
                key={x.value}
                type="button"
                aria-pressed={on}
                onClick={() => toggleExtra(x.value)}
                className={`cursor-pointer rounded-full border px-3 py-1 text-xs transition-colors ${
                  on ? 'border-[#C5A77B] bg-[#C5A77B]/15 text-[#E8D3B0]' : 'border-[#2A2F38] text-[#9AA3B2] hover:text-white'
                }`}
              >
                {x.label}
              </button>
            );
          })}
        </div>
        {extras.includes('pool') && (
          <div className="mt-3">
            <label htmlFor="fp-pool" className={labelCls}>Pool position</label>
            <select id="fp-pool" {...register('pool_layout')} className={inputCls}>
              <option value="">as described (default: beside the house)</option>
              {POOL_LAYOUTS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label} – {p.hint}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="fp-project" className={labelCls}>Project name (title block)</label>
          <input id="fp-project" {...register('project_name')} className={inputCls} />
        </div>
        <div>
          <label htmlFor="fp-owner" className={labelCls}>Owner (title block)</label>
          <input id="fp-owner" {...register('owner_name')} className={inputCls} />
        </div>
      </div>

      <Button type="submit" variant="accent" loading={busy} disabled={busy} leftIcon={<IconSparkles className="h-4 w-4" />}>
        Check my brief
      </Button>
    </form>
  );
}
