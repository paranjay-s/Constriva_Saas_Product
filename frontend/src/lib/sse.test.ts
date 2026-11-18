import { beforeEach, describe, expect, it } from 'vitest';
import { TOKEN_STORAGE_KEY } from './api';
import { authHeaders, parseSse } from './sse';

describe('parseSse', () => {
  it('parses comments, named events and multi-line data', () => {
    const { messages, rest } = parseSse(': keep-alive\n\nevent: complete\ndata: line1\ndata: line2\n\ndata: tail');
    expect(messages).toEqual([{ event: 'complete', data: 'line1\nline2' }]);
    expect(rest).toBe('data: tail');
  });

  it('joins a message that arrives split across chunks', () => {
    const first = parseSse('event: progress\ndata: {"a"');
    expect(first.messages).toEqual([]);
    const second = parseSse(`${first.rest}:1}\n\nevent: prog`);
    expect(second.messages).toEqual([{ event: 'progress', data: '{"a":1}' }]);
    const third = parseSse(`${second.rest}ress\ndata: {"a":2}\n\n`);
    expect(third.messages).toEqual([{ event: 'progress', data: '{"a":2}' }]);
    expect(third.rest).toBe('');
  });
});

describe('authHeaders', () => {
  beforeEach(() => localStorage.clear());

  it("carries the session's token, and nothing when nobody is signed in", () => {
    expect(authHeaders().has('Authorization')).toBe(false);
    localStorage.setItem(TOKEN_STORAGE_KEY, 'test-jwt-token');
    expect(authHeaders().get('Authorization')).toBe('Bearer test-jwt-token');
  });
});
