import { describe, expect, it } from 'vitest';
import type { ChatMessage } from '@/types/api';
import {
  NOT_IN_RADIAAI_NOTICE,
  RADIAAI_ENTER_NOTICE,
  RADIAAI_EXIT_NOTICE,
  buildApiHistory,
  deriveChatMode,
  parseChatCommand,
  planChatSend,
} from './chatMode';

const user = (content: string): ChatMessage => ({ role: 'user', content });
const assistant = (content: string): ChatMessage => ({ role: 'assistant', content });

describe('parseChatCommand', () => {
  it('recognizes /radiaai with and without a question, case-insensitively', () => {
    expect(parseChatCommand('/radiaai')).toEqual({ kind: 'enter', question: '' });
    expect(parseChatCommand('  /RadiaAI  show SRS-42 ')).toEqual({ kind: 'enter', question: 'show SRS-42' });
    expect(parseChatCommand('/exit')).toEqual({ kind: 'exit' });
    expect(parseChatCommand('/EXIT ')).toEqual({ kind: 'exit' });
  });

  it('ignores non-commands and look-alikes', () => {
    expect(parseChatCommand('what is /radiaai?')).toBeNull();
    expect(parseChatCommand('/radiaaix')).toBeNull();
    expect(parseChatCommand('/exit now')).toBeNull();
  });
});

describe('deriveChatMode', () => {
  it('defaults to standards and follows the last command', () => {
    expect(deriveChatMode([])).toBe('standards');
    expect(deriveChatMode([user('/radiaai'), assistant(RADIAAI_ENTER_NOTICE)])).toBe('radiaai');
    expect(deriveChatMode([user('/radiaai q'), assistant('a'), user('/exit')])).toBe('standards');
  });
});

describe('buildApiHistory', () => {
  it('only includes turns from the current mode segment, without commands or notices', () => {
    const history = [
      user('standards q'),
      assistant('standards a'),
      user('/radiaai parent of SRS-42?'),
      assistant('SRS-1'),
    ];
    expect(buildApiHistory(history, 10)).toEqual([user('parent of SRS-42?'), assistant('SRS-1')]);
  });

  it('starts a fresh standards segment after /exit', () => {
    const history = [user('/radiaai'), assistant(RADIAAI_ENTER_NOTICE), user('q'), assistant('a'), user('/exit'), assistant(RADIAAI_EXIT_NOTICE)];
    expect(buildApiHistory(history, 10)).toEqual([]);
  });

  it('caps to the limit', () => {
    const history = [user('1'), assistant('2'), user('3')];
    expect(buildApiHistory(history, 2)).toEqual([assistant('2'), user('3')]);
  });
});

describe('planChatSend', () => {
  it('routes ordinary questions to the standards checker', () => {
    expect(planChatSend([user('a'), assistant('b')], 'how to write?', 10)).toEqual({
      kind: 'ask',
      question: 'how to write?',
      mode: 'standards',
      history: [user('a'), assistant('b')],
    });
  });

  it('handles bare commands locally', () => {
    expect(planChatSend([], '/radiaai', 10)).toEqual({ kind: 'local', notice: RADIAAI_ENTER_NOTICE });
    expect(planChatSend([user('/radiaai')], '/exit', 10)).toEqual({ kind: 'local', notice: RADIAAI_EXIT_NOTICE });
    expect(planChatSend([], '/exit', 10)).toEqual({ kind: 'local', notice: NOT_IN_RADIAAI_NOTICE });
  });

  it('asks /radiaai <question> in RadiaAI mode with no prior history', () => {
    expect(planChatSend([user('x'), assistant('y')], '/radiaai children of SRS-42', 10)).toEqual({
      kind: 'ask',
      question: 'children of SRS-42',
      mode: 'radiaai',
      history: [],
    });
  });

  it('keeps asking in RadiaAI mode until /exit', () => {
    const history = [user('/radiaai'), assistant(RADIAAI_ENTER_NOTICE), user('q1'), assistant('a1')];
    expect(planChatSend(history, 'q2', 10)).toEqual({
      kind: 'ask',
      question: 'q2',
      mode: 'radiaai',
      history: [user('q1'), assistant('a1')],
    });
  });
});
