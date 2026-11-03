/**
 * Floating chatbot widget - a fixed icon button in the bottom-right corner
 * that expands into a small messaging window. It shares the user's
 * persisted conversation with the Chat page (see useChatHistory), so it is
 * retained across page navigation and reloads.
 */

import { useState } from 'react';
import Badge from '@mui/material/Badge';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Divider from '@mui/material/Divider';
import Fab from '@mui/material/Fab';
import IconButton from '@mui/material/IconButton';
import Link from '@mui/material/Link';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import CloseIcon from '@mui/icons-material/Close';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import ForumIcon from '@mui/icons-material/Forum';
import HubIcon from '@mui/icons-material/Hub';
import SendIcon from '@mui/icons-material/Send';
import { AnimatePresence, motion } from 'framer-motion';
import { useChatStream } from '@/hooks/useChatStream';
import { useChatHistory } from '@/hooks/useChatHistory';
import { useAppContext } from '@/context/useAppContext';
import type { ChatSource } from '@/types/api';
import { MessageText } from '@/components/chat/MessageText';
import { ChatConversation } from '@/components/chat/ChatConversation';
import { RadiaModeToggle } from '@/components/chat/RadiaModeToggle';
import { changeChatMode, deriveChatMode, planChatSend } from '@/utils/chatMode';

const WIDGET_WIDTH = 360;
const WIDGET_HEIGHT = 500;
const HISTORY_TURNS_SENT_TO_API = 10;

/** Per-turn MCP metadata, kept separately from the persisted chat history so the
 * localStorage schema (ChatMessage: role + content only) never changes shape. */
interface McpTurnInfo {
  usedMcp: boolean;
  sources: ChatSource[];
}

export function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [openCount, setOpenCount] = useState(0);
  const [input, setInput] = useState('');
  const { history, setHistory, clearHistory } = useChatHistory();
  const [mcpInfoByIndex, setMcpInfoByIndex] = useState<Record<number, McpTurnInfo>>({});
  const { motionPreference } = useAppContext();
  const { isStreaming, streamingText, sendMessage } = useChatStream();

  const reduceMotion = motionPreference === 'reduced';
  const isRadiaMode = deriveChatMode(history) === 'radiaai';

  const handleOpen = () => {
    setOpenCount((count) => count + 1);
    setOpen(true);
  };

  const handleSend = () => {
    const text = input.trim();
    if (!text || isStreaming) return;

    const plan = planChatSend(history, text, HISTORY_TURNS_SENT_TO_API);
    const updatedHistory = [...history, { role: 'user' as const, content: text }];
    setInput('');

    if (plan.kind === 'local') {
      setHistory([...updatedHistory, { role: 'assistant', content: plan.notice }]);
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
        },
        onError: (message) => {
          setHistory((prev) => [...prev, { role: 'assistant', content: `Error: ${message}` }]);
        },
      }
    );
  };

  return (
    <Box
      sx={{
        position: 'fixed',
        bottom: { xs: 16, sm: 24 },
        right: { xs: 16, sm: 24 },
        zIndex: (t) => t.zIndex.modal + 1,
      }}
    >
      <AnimatePresence>
        {open && (
          <motion.div
            initial={reduceMotion ? false : { opacity: 0, y: 16, scale: 0.96 }}
            animate={reduceMotion ? {} : { opacity: 1, y: 0, scale: 1 }}
            exit={reduceMotion ? {} : { opacity: 0, y: 16, scale: 0.96 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
            style={{ transformOrigin: 'bottom right' }}
          >
            <Paper
              elevation={8}
              sx={{
                width: WIDGET_WIDTH,
                height: WIDGET_HEIGHT,
                maxWidth: 'calc(100vw - 32px)',
                maxHeight: 'calc(100vh - 120px)',
                mb: 2,
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                borderRadius: 3,
              }}
            >
              {/* Header */}
              <Box
                display="flex"
                alignItems="center"
                justifyContent="space-between"
                px={1.5}
                py={1.5}
                sx={{
                  bgcolor: 'primary.main',
                  color: 'primary.contrastText',
                  '& .MuiSwitch-switchBase.Mui-checked': { color: 'primary.contrastText' },
                  '& .MuiSwitch-track, & .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                    bgcolor: 'primary.contrastText',
                  },
                }}
              >
                <Box display="flex" alignItems="center" gap={0.5}>
                  <ForumIcon fontSize="small" />
                  <Typography variant="subtitle1" fontWeight={700}>
                    Chat
                  </Typography>
                </Box>
                <Box display="flex" alignItems="center" gap={0.5}>
                  <RadiaModeToggle
                    checked={isRadiaMode}
                    disabled={isStreaming}
                    onChange={(checked) => {
                      setHistory((prev) => changeChatMode(prev, checked ? 'radiaai' : 'standards'));
                    }}
                  />
                  <Tooltip title="Clear conversation">
                    <span>
                      <IconButton
                        size="small"
                        onClick={clearHistory}
                        disabled={history.length === 0}
                        sx={{ color: 'inherit' }}
                      >
                        <DeleteOutlineIcon fontSize="small" />
                      </IconButton>
                    </span>
                  </Tooltip>
                  <Tooltip title="Close">
                    <IconButton size="small" onClick={() => setOpen(false)} sx={{ color: 'inherit' }}>
                      <CloseIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Box>
              </Box>

              {/* Conversation area */}
              <ChatConversation key={openCount} padding={1.5} reduceMotion={reduceMotion}>
                {history.length === 0 && (
                  <Box
                    display="flex"
                    flexDirection="column"
                    alignItems="center"
                    justifyContent="center"
                    height="100%"
                    gap={1}
                    color="text.secondary"
                    textAlign="center"
                    px={2}
                  >
                    <ForumIcon fontSize="large" />
                    <Typography variant="body2">
                      Ask a question about how to write requirements.
                    </Typography>
                    <Typography variant="caption">
                      Turn on Radia AI to ask about live engineering data.
                    </Typography>
                  </Box>
                )}

                {history.map((turn, i) => (
                  <Box
                    key={i}
                    mb={1.5}
                    display="flex"
                    flexDirection="column"
                    alignItems={turn.role === 'user' ? 'flex-end' : 'flex-start'}
                  >
                    <Paper
                      elevation={0}
                      sx={{
                        p: 1.5,
                        maxWidth: '85%',
                        minWidth: 0,
                        bgcolor: turn.role === 'user' ? 'primary.main' : 'background.paper',
                        color: turn.role === 'user' ? 'primary.contrastText' : 'text.primary',
                        border: turn.role === 'assistant' ? '1px solid' : 'none',
                        borderColor: 'divider',
                      }}
                    >
                      <Typography
                        variant="body2"
                        sx={{
                          whiteSpace: 'pre-wrap',
                          overflowWrap: 'anywhere',
                          wordBreak: 'break-word',
                        }}
                      >
                        <MessageText content={turn.content} />
                      </Typography>
                    </Paper>
                    {mcpInfoByIndex[i]?.usedMcp && (
                      <Stack direction="row" spacing={0.5} alignItems="center" flexWrap="wrap" mt={0.5}>
                        <Chip
                          icon={<HubIcon fontSize="small" />}
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
                  <Box mb={1.5} display="flex" flexDirection="column" alignItems="flex-start">
                    <Paper
                      elevation={0}
                      sx={{
                        p: 1.5,
                        maxWidth: '85%',
                        minWidth: 0,
                        bgcolor: 'background.paper',
                        border: '1px solid',
                        borderColor: 'divider',
                      }}
                    >
                      <Typography
                        variant="body2"
                        sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', wordBreak: 'break-word' }}
                      >
                        <MessageText content={streamingText} />
                      </Typography>
                    </Paper>
                  </Box>
                )}

                {isStreaming && !streamingText && (
                  <Box display="flex" alignItems="center" gap={1} color="text.secondary">
                    <CircularProgress size={14} />
                    <Typography variant="caption">Thinking…</Typography>
                  </Box>
                )}
              </ChatConversation>

              <Divider />

              {/* Input area */}
              <Box display="flex" gap={1} p={1.5}>
                <TextField
                  fullWidth
                  multiline
                  maxRows={3}
                  placeholder={isRadiaMode ? 'Ask about engineering data…' : 'Ask a question…'}
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
                  <SendIcon fontSize="small" />
                </IconButton>
              </Box>
            </Paper>
          </motion.div>
        )}
      </AnimatePresence>

      {!open && (
        <Tooltip title="Ask Radia AI">
          <Badge color="secondary" variant="dot" invisible={history.length === 0}>
            <Fab color="primary" onClick={handleOpen} aria-label="Open chat">
              <ForumIcon />
            </Fab>
          </Badge>
        </Tooltip>
      )}
    </Box>
  );
}
