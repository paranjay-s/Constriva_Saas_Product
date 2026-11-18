/**
 * Server-Sent Events read with fetch().
 *
 * Every stream of this API needs the signed-in user's token, and EventSource cannot send
 * an Authorization header. fetch() can, so streams are read from the response body, and
 * the text that arrives is split into messages here.
 */
import { TOKEN_STORAGE_KEY } from './api';

export interface SseMessage {
  event: string;
  data: string;
}

/** Split an SSE text buffer into complete messages; returns them and the unfinished rest. */
export function parseSse(buffer: string): { messages: SseMessage[]; rest: string } {
  const messages: SseMessage[] = [];
  const blocks = buffer.replace(/\r\n/g, '\n').split('\n\n');
  const rest = blocks.pop() ?? '';
  for (const block of blocks) {
    let event = 'message';
    const data: string[] = [];
    for (const line of block.split('\n')) {
      if (line.startsWith(':')) continue; // keep-alive comment
      if (line.startsWith('event:')) event = line.slice(6).trim();
      else if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
    }
    if (data.length) messages.push({ event, data: data.join('\n') });
  }
  return { messages, rest };
}

/** The Authorization header of the current session; empty when nobody is signed in. */
export function authHeaders(): Headers {
  const headers = new Headers();
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return headers;
}
