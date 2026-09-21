/**
 * Floating chatbot widget - a fixed icon button in the bottom-right corner
 * that expands into a small messaging window. Conversation history is
 * persisted (see useChatWidgetHistory) so it is retained across page
 * navigation and reloads.
 */

import { useEffect, useRef, useState } from 'react';
import Badge from '@mui/material/Badge';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Divider from '@mui/material/Divider';
import Fab from '@mui/material/Fab';
import IconButton from '@mui/material/IconButton';
import Paper from '@mui/material/Paper';
import Tooltip from '@mui/material/Tooltip';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import CloseIcon from '@mui/icons-material/Close';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import ForumIcon from '@mui/icons-material/Forum';
import SendIcon from '@mui/icons-material/Send';
import { AnimatePresence, motion } from 'framer-motion';
import { useChatStream } from '@/hooks/useChatStream';
import { useChatWidgetHistory } from '@/hooks/useChatWidgetHistory';
import { useAppContext } from '@/context/useAppContext';
import type { ChatMessage } from '@/types/api';

const WIDGET_WIDTH = 360;
const WIDGET_HEIGHT = 500;
const HISTORY_TURNS_SENT_TO_API = 10;

export function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const { history, setHistory, clearHistory } = useChatWidgetHistory();
  const { motionPreference } = useAppContext();
  const { isStreaming, streamingText, sendMessage } = useChatStream();
  const endRef = useRef<HTMLDivElement>(null);

  const reduceMotion = motionPreference === 'reduced';

  const scrollToEnd = () => {
    setTimeout(() => endRef.current?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth' }), 50);
  };

  const handleOpen = () => {
    setOpen(true);
    scrollToEnd();
  };

  // Keep the conversation pinned to the bottom as the streamed answer grows.
  useEffect(() => {
    if (streamingText) scrollToEnd();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [streamingText]);

  const handleSend = () => {
    const question = input.trim();
    if (!question || isStreaming) return;

    const updatedHistory = [...history, { role: 'user' as const, content: question }];
    setHistory(updatedHistory);
    setInput('');
    scrollToEnd();

    const apiHistory: ChatMessage[] = updatedHistory
      .slice(-HISTORY_TURNS_SENT_TO_API)
      .map((t) => ({ role: t.role, content: t.content }));

    sendMessage(
      { question, conversation_history: apiHistory, citation_style: 'none' },
      {
        onDone: (data) => {
          setHistory((prev) => [...prev, { role: 'assistant', content: data.answer }]);
          scrollToEnd();
        },
        onError: (message) => {
          setHistory((prev) => [...prev, { role: 'assistant', content: `Error: ${message}` }]);
          scrollToEnd();
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
                px={2}
                py={1.5}
                sx={{ bgcolor: 'primary.main', color: 'primary.contrastText' }}
              >
                <Box display="flex" alignItems="center" gap={1}>
                  <ForumIcon fontSize="small" />
                  <Typography variant="subtitle1" fontWeight={700}>
                    Ask Radia AI
                  </Typography>
                </Box>
                <Box>
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
              <Box
                flexGrow={1}
                overflow="auto"
                sx={{ overflowX: 'hidden', bgcolor: 'background.default' }}
                p={1.5}
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
                    textAlign="center"
                    px={2}
                  >
                    <ForumIcon fontSize="large" />
                    <Typography variant="body2">
                      Ask a question about how to write requirements.
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
                        {turn.content}
                      </Typography>
                    </Paper>
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
                        {streamingText}
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

                <div ref={endRef} />
              </Box>

              <Divider />

              {/* Input area */}
              <Box display="flex" gap={1} p={1.5}>
                <TextField
                  fullWidth
                  multiline
                  maxRows={3}
                  placeholder="Ask a question…"
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
