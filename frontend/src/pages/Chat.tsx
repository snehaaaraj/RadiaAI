import { useState, useRef, useEffect } from 'react';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import TextField from '@mui/material/TextField';
import IconButton from '@mui/material/IconButton';
import Typography from '@mui/material/Typography';
import Divider from '@mui/material/Divider';
import CircularProgress from '@mui/material/CircularProgress';
import Chip from '@mui/material/Chip';
import Link from '@mui/material/Link';
import Stack from '@mui/material/Stack';
import SendIcon from '@mui/icons-material/Send';
import BoltIcon from '@mui/icons-material/Bolt';
import HubIcon from '@mui/icons-material/Hub';
import { useChatStream } from '@/hooks/useChatStream';
import { useChatHistory } from '@/hooks/useChatHistory';
import type { ChatSource } from '@/types/api';
import { MessageText } from '@/components/chat/MessageText';
import { deriveChatMode, planChatSend } from '@/utils/chatMode';

const HISTORY_TURNS_SENT_TO_API = 10;

interface ConversationTurn {
  role: 'user' | 'assistant';
  content: string;
}

/** Per-turn MCP metadata, kept separately from the persisted chat history so the
 * localStorage schema (ChatMessage: role + content only) never changes shape. */
interface McpTurnInfo {
  usedMcp: boolean;
  sources: ChatSource[];
}

export default function Chat() {
  const [input, setInput] = useState('');
  const { history, setHistory } = useChatHistory();
  const [mcpInfoByIndex, setMcpInfoByIndex] = useState<Record<number, McpTurnInfo>>({});
  const endRef = useRef<HTMLDivElement>(null);
  const { isStreaming, streamingText, sendMessage } = useChatStream();
  const isRadiaMode = deriveChatMode(history) === 'radiaai';

  const scrollToEnd = () => setTimeout(() => endRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);

  // Keep the conversation pinned to the bottom as the streamed answer grows.
  useEffect(() => {
    if (streamingText) scrollToEnd();
  }, [streamingText]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || isStreaming) return;

    const plan = planChatSend(history, text, HISTORY_TURNS_SENT_TO_API);
    const userTurn: ConversationTurn = { role: 'user', content: text };
    const updatedHistory = [...history, userTurn];
    setInput('');

    if (plan.kind === 'local') {
      setHistory([...updatedHistory, { role: 'assistant', content: plan.notice }]);
      scrollToEnd();
      return;
    }

    setHistory(updatedHistory);

    sendMessage(
      {
        question: plan.question,
        conversation_history: plan.history,
        citation_style: 'none',
        mode: plan.mode,
      },
      {
        onDone: (data) => {
          setHistory((prev) => {
            const next = [...prev, { role: 'assistant' as const, content: data.answer }];
            if (data.used_mcp) {
              const index = next.length - 1;
              setMcpInfoByIndex((info) => ({
                ...info,
                [index]: { usedMcp: true, sources: data.sources ?? [] },
              }));
            }
            return next;
          });
          scrollToEnd();
        },
        onError: (message) => {
          setHistory((prev) => [...prev, { role: 'assistant', content: `Error: ${message}` }]);
        },
      }
    );
  };

  return (
    <Box display="flex" flexDirection="column" flexGrow={1} minHeight={0}>
      <Typography variant="h5" fontWeight={700} mb={2} flexShrink={0}>
        Chat
      </Typography>

      {/* Conversation area - the only part of this page that scrolls. */}
      <Paper
        variant="outlined"
        sx={{ flexGrow: 1, minHeight: 0, overflow: 'auto', p: 2, mb: 2, bgcolor: 'background.default' }}
      >
        {history.length === 0 && (
          <Box
            display="flex"
            flexDirection="column"
            alignItems="center"
            justifyContent="center"
            height="100%"
            gap={1}
            color="text.secondary"
          >
            <BoltIcon fontSize="large" />
            <Typography>Ask a question about your documents</Typography>
            <Typography variant="body2">
              Type /radiaai to ask about live engineering data, /exit to return.
            </Typography>
          </Box>
        )}

        {history.map((turn, i) => (
          <Box
            key={i}
            mb={2}
            display="flex"
            flexDirection="column"
            alignItems={turn.role === 'user' ? 'flex-end' : 'flex-start'}
          >
            <Paper
              elevation={0}
              sx={{
                p: 2,
                maxWidth: '75%',
                bgcolor: turn.role === 'user' ? 'primary.main' : 'background.paper',
                color: turn.role === 'user' ? 'white' : 'text.primary',
                border: turn.role === 'assistant' ? '1px solid' : 'none',
                borderColor: 'divider',
              }}
            >
              <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
                <MessageText content={turn.content} />
              </Typography>
            </Paper>
            {mcpInfoByIndex[i]?.usedMcp && (
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" mt={0.5}>
                <Chip
                  icon={<HubIcon />}
                  label="Engineering data"
                  size="small"
                  color="info"
                  variant="outlined"
                />
                {mcpInfoByIndex[i].sources.map((source) => (
                  <Link
                    key={source.url}
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    variant="caption"
                  >
                    {source.label}
                  </Link>
                ))}
              </Stack>
            )}
          </Box>
        ))}

        {isStreaming && streamingText && (
          <Box mb={2} display="flex" flexDirection="column" alignItems="flex-start">
            <Paper
              elevation={0}
              sx={{ p: 2, maxWidth: '75%', border: '1px solid', borderColor: 'divider' }}
            >
              <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
                <MessageText content={streamingText} />
              </Typography>
            </Paper>
          </Box>
        )}

        {isStreaming && !streamingText && (
          <Box display="flex" alignItems="center" gap={1} color="text.secondary">
            <CircularProgress size={16} />
            <Typography variant="body2">Thinking…</Typography>
          </Box>
        )}

        <div ref={endRef} />
      </Paper>

      <Divider sx={{ flexShrink: 0 }} />

      {isRadiaMode && (
        <Box pt={1} flexShrink={0}>
          <Chip
            icon={<HubIcon />}
            label="RadiaAI mode · type /exit to leave"
            size="small"
            color="info"
          />
        </Box>
      )}

      {/* Input area */}
      <Box display="flex" gap={1} pt={2} flexShrink={0}>
        <TextField
          fullWidth
          multiline
          maxRows={4}
          placeholder={
            isRadiaMode ? 'Ask about engineering data…' : 'Ask a question about your documents…'
          }
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          disabled={isStreaming}
          size="small"
        />
        <IconButton
          color="primary"
          onClick={handleSend}
          disabled={isStreaming || !input.trim()}
          sx={{ alignSelf: 'flex-end' }}
        >
          <SendIcon />
        </IconButton>
      </Box>
    </Box>
  );
}
