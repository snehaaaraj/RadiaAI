import { useState, useRef } from 'react';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import TextField from '@mui/material/TextField';
import IconButton from '@mui/material/IconButton';
import Typography from '@mui/material/Typography';
import Divider from '@mui/material/Divider';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import SendIcon from '@mui/icons-material/Send';
import BoltIcon from '@mui/icons-material/Bolt';
import { useChat } from '@/hooks/useChat';
import type { ChatMessage } from '@/types/api';

interface ConversationTurn {
  role: 'user' | 'assistant';
  content: string;
  citations?: Array<{ filename: string; section: string; score: number }>;
}

export default function Chat() {
  const [input, setInput] = useState('');
  const [history, setHistory] = useState<ConversationTurn[]>([]);
  const endRef = useRef<HTMLDivElement>(null);
  const { mutate: sendMessage, isPending } = useChat();

  const handleSend = () => {
    const question = input.trim();
    if (!question || isPending) return;

    const userTurn: ConversationTurn = { role: 'user', content: question };
    const updatedHistory = [...history, userTurn];
    setHistory(updatedHistory);
    setInput('');

    const apiHistory: ChatMessage[] = updatedHistory
      .slice(-10)
      .map((t) => ({ role: t.role, content: t.content }));

    sendMessage(
      { question, conversation_history: apiHistory },
      {
        onSuccess: (data) => {
          setHistory((prev) => [
            ...prev,
            {
              role: 'assistant',
              content: data.answer,
              citations: data.citations.map((c) => ({
                filename: c.filename,
                section: c.section,
                score: c.score,
              })),
            },
          ]);
          setTimeout(() => endRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
        },
        onError: (err) => {
          setHistory((prev) => [
            ...prev,
            { role: 'assistant', content: `Error: ${(err as Error).message}` },
          ]);
        },
      }
    );
  };

  return (
    <Box display="flex" flexDirection="column" height="calc(100vh - 120px)">
      <Typography variant="h5" fontWeight={700} mb={2}>
        Chat
      </Typography>

      {/* Conversation area */}
      <Paper
        variant="outlined"
        sx={{ flexGrow: 1, overflow: 'auto', p: 2, mb: 2, bgcolor: 'background.default' }}
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
                {turn.content}
              </Typography>

              {turn.citations && turn.citations.length > 0 && (
                <Box mt={1.5} display="flex" gap={0.5} flexWrap="wrap">
                  {turn.citations.map((c, ci) => (
                    <Chip
                      key={ci}
                      label={`${c.filename}${c.section ? ' — ' + c.section : ''}`}
                      size="small"
                      variant="outlined"
                    />
                  ))}
                </Box>
              )}
            </Paper>
          </Box>
        ))}

        {isPending && (
          <Box display="flex" alignItems="center" gap={1} color="text.secondary">
            <CircularProgress size={16} />
            <Typography variant="body2">Thinking…</Typography>
          </Box>
        )}

        <div ref={endRef} />
      </Paper>

      <Divider />

      {/* Input area */}
      <Box display="flex" gap={1} pt={2}>
        <TextField
          fullWidth
          multiline
          maxRows={4}
          placeholder="Ask a question about your documents…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          disabled={isPending}
          size="small"
        />
        <IconButton
          color="primary"
          onClick={handleSend}
          disabled={isPending || !input.trim()}
          sx={{ alignSelf: 'flex-end' }}
        >
          <SendIcon />
        </IconButton>
      </Box>
    </Box>
  );
}
