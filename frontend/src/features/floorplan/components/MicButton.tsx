import type { SpeechInput } from '../hooks/useSpeechInput';

/** Round mic toggle; hidden when the browser has no speech recognition. */
export function MicButton({ speech, label = 'Speak' }: { speech: SpeechInput; label?: string }) {
  if (!speech.supported) return null;
  const on = speech.listening;
  return (
    <button
      type="button"
      onClick={on ? speech.stop : speech.start}
      aria-pressed={on}
      aria-label={on ? 'Stop voice input' : `${label} instead of typing`}
      title={on ? 'Stop listening' : 'Speak instead of typing'}
      className={`relative inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border transition-colors cursor-pointer ${
        on
          ? 'border-[#E5484D] bg-[#E5484D]/15 text-[#FF8A8D]'
          : 'border-[#303540] bg-[#1C1F26] text-[#C5A77B] hover:border-[#C5A77B]'
      }`}
    >
      {on && <span className="absolute inset-0 animate-ping rounded-full bg-[#E5484D]/20" aria-hidden />}
      <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
        <rect x="9" y="3" width="6" height="11" rx="3" />
        <path d="M5 11a7 7 0 0 0 14 0M12 18v3" strokeLinecap="round" />
      </svg>
    </button>
  );
}
