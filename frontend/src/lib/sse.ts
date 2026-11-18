/**
 * Server-Sent Events read with fetch().
 *
 * Every stream of this API needs the signed-in user's token, and EventSource cannot send
 * an Authorization header. fetch() can, so a feature reads its stream from the response
 * body and splits the text that arrives into messages here.
 */
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
