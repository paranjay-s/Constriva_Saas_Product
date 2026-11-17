/**
 * Voice typing with the browser's Web Speech API (Chrome, Edge, Safari). Nothing is sent
 * to our servers; the browser turns speech into text and we put it in the text box.
 * Where the API is missing (e.g. Firefox), `supported` is false and the mic is hidden.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

interface SpeechAlternative {
  transcript: string;
}
interface SpeechResult {
  isFinal: boolean;
  0: SpeechAlternative;
}
interface SpeechResultEvent {
  resultIndex: number;
  results: ArrayLike<SpeechResult>;
}
interface SpeechErrorEvent {
  error: string;
}
interface Recognition {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((e: SpeechResultEvent) => void) | null;
  onerror: ((e: SpeechErrorEvent) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}
type RecognitionCtor = new () => Recognition;

function recognitionCtor(): RecognitionCtor | null {
  if (typeof window === 'undefined') return null;
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

const ERRORS: Record<string, string> = {
  'not-allowed': 'Microphone permission was denied. Allow it in the browser to use voice.',
  'service-not-allowed': 'Voice input is blocked in this browser.',
  'no-speech': 'No speech was heard. Try again.',
  'audio-capture': 'No microphone was found.',
  network: 'Voice input needs an internet connection.',
};

export interface SpeechInput {
  supported: boolean;
  listening: boolean;
  interim: string;
  error: string | null;
  start: () => void;
  stop: () => void;
}

/** onFinal receives each finished phrase; append it to the text box. */
export function useSpeechInput(onFinal: (text: string) => void, lang = 'en-IN'): SpeechInput {
  const Ctor = recognitionCtor();
  const recRef = useRef<Recognition | null>(null);
  const onFinalRef = useRef(onFinal);
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    onFinalRef.current = onFinal;
  }, [onFinal]);

  const stop = useCallback(() => {
    recRef.current?.stop();
  }, []);

  const start = useCallback(() => {
    if (!Ctor || recRef.current) return;
    const rec = new Ctor();
    rec.lang = lang;
    rec.continuous = true;
    rec.interimResults = true;
    rec.onresult = (e) => {
      let partial = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) onFinalRef.current(r[0].transcript.trim());
        else partial += r[0].transcript;
      }
      setInterim(partial);
    };
    rec.onerror = (e) => setError(ERRORS[e.error] ?? `Voice input stopped (${e.error}).`);
    rec.onend = () => {
      recRef.current = null;
      setListening(false);
      setInterim('');
    };
    setError(null);
    recRef.current = rec;
    rec.start();
    setListening(true);
  }, [Ctor, lang]);

  useEffect(() => () => recRef.current?.stop(), []);

  return { supported: Ctor !== null, listening, interim, error, start, stop };
}
