/**
 * Chat routing between the two fully separate backend pipelines:
 *
 * - 'standards' (default): answers from the indexed standards documents.
 * - 'radiaai': entered by a message starting with `/radiaai`, left with `/exit`;
 *   answers only from mcp-radia live engineering data (e.g. Jama).
 *
 * The active mode is derived from the command turns already in the persisted
 * conversation, so it is shared by the Chat page and the pop-up widget and
 * survives reloads without a separate store. Each command also starts a fresh
 * context segment: only turns since the last command are sent as history, so
 * standards answers never leak into a RadiaAI question (or vice versa).
 */

import type { ChatMessage } from '@/types/api';

export type ChatMode = 'standards' | 'radiaai';

export const RADIAAI_COMMAND = '/radiaai';
export const EXIT_COMMAND = '/exit';

export const RADIAAI_ENTER_NOTICE =
  'RadiaAI mode is on. Your questions now go to live engineering data (Jama). Type /exit to return to the standards checker.';
export const RADIAAI_EXIT_NOTICE =
  'Exited RadiaAI mode. Your questions now go to the standards checker.';
export const NOT_IN_RADIAAI_NOTICE =
  'You are not in RadiaAI mode. Type /radiaai to ask about live engineering data.';

const LOCAL_NOTICES = new Set([RADIAAI_ENTER_NOTICE, RADIAAI_EXIT_NOTICE, NOT_IN_RADIAAI_NOTICE]);

export type ChatCommand = { kind: 'enter'; question: string } | { kind: 'exit' };

/** Parse `/radiaai [question]` or `/exit` (case-insensitive); anything else is not a command. */
export function parseChatCommand(text: string): ChatCommand | null {
  const trimmed = text.trim();
  const enter = /^\/radiaai(?:\s+([\s\S]*))?$/i.exec(trimmed);
  if (enter) return { kind: 'enter', question: (enter[1] ?? '').trim() };
  if (/^\/exit$/i.test(trimmed)) return { kind: 'exit' };
  return null;
}

/** Index of the last command turn in the history, or -1 if none. */
function lastCommandIndex(history: ChatMessage[]): number {
  for (let i = history.length - 1; i >= 0; i--) {
    const turn = history[i];
    if (turn.role === 'user' && parseChatCommand(turn.content)) return i;
  }
  return -1;
}

/** The mode in effect after the given conversation. */
export function deriveChatMode(history: ChatMessage[]): ChatMode {
  const index = lastCommandIndex(history);
  if (index === -1) return 'standards';
  return parseChatCommand(history[index].content)?.kind === 'enter' ? 'radiaai' : 'standards';
}

/**
 * Conversation history to send with the next question: only turns from the
 * current mode's segment, with command turns reduced to their question (if
 * any) and local mode notices dropped, capped to the last `limit` turns.
 */
export function buildApiHistory(history: ChatMessage[], limit: number): ChatMessage[] {
  const start = Math.max(lastCommandIndex(history), 0);
  const segment: ChatMessage[] = [];
  for (const turn of history.slice(start)) {
    if (turn.role === 'assistant' && LOCAL_NOTICES.has(turn.content)) continue;
    const command = turn.role === 'user' ? parseChatCommand(turn.content) : null;
    if (command) {
      if (command.kind === 'enter' && command.question) {
        segment.push({ role: 'user', content: command.question });
      }
      continue;
    }
    segment.push({ role: turn.role, content: turn.content });
  }
  return segment.slice(-limit);
}

export type ChatSendPlan =
  | { kind: 'local'; notice: string }
  | { kind: 'ask'; question: string; mode: ChatMode; history: ChatMessage[] };

/**
 * Decide what to do with a submitted message, given the history *before* it.
 * Commands without a question only switch modes locally; everything else is
 * asked in the mode in effect after this message.
 */
export function planChatSend(history: ChatMessage[], text: string, limit: number): ChatSendPlan {
  const command = parseChatCommand(text);
  if (command?.kind === 'exit') {
    return {
      kind: 'local',
      notice: deriveChatMode(history) === 'radiaai' ? RADIAAI_EXIT_NOTICE : NOT_IN_RADIAAI_NOTICE,
    };
  }
  if (command?.kind === 'enter') {
    if (!command.question) return { kind: 'local', notice: RADIAAI_ENTER_NOTICE };
    return { kind: 'ask', question: command.question, mode: 'radiaai', history: [] };
  }
  return {
    kind: 'ask',
    question: text.trim(),
    mode: deriveChatMode(history),
    history: buildApiHistory(history, limit),
  };
}
