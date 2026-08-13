import { useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import TextField from '@mui/material/TextField';
import Button from '@mui/material/Button';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Divider from '@mui/material/Divider';
import Chip from '@mui/material/Chip';
import { useMutation } from '@tanstack/react-query';
import { searchDocuments } from '@/api/search';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import type { SearchMode, SearchResult } from '@/types/api';

export default function Search() {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<SearchMode>('hybrid');

  const { mutate: runSearch, data, isPending, isError, error } = useMutation({
    mutationFn: () => searchDocuments({ query, mode, top_k: 10 }),
  });

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} mb={3}>
        Document Search
      </Typography>

      {/* Search controls */}
      <Box display="flex" gap={2} mb={3} flexWrap="wrap" alignItems="flex-start">
        <TextField
          sx={{ flexGrow: 1, minWidth: 300 }}
          placeholder="Search documents…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && query.trim() && runSearch()}
          size="small"
        />

        <ToggleButtonGroup
          value={mode}
          exclusive
          onChange={(_, v) => v && setMode(v)}
          size="small"
        >
          <ToggleButton value="keyword">Keyword</ToggleButton>
          <ToggleButton value="vector">Vector</ToggleButton>
          <ToggleButton value="hybrid">Hybrid</ToggleButton>
        </ToggleButtonGroup>

        <Button
          variant="contained"
          onClick={() => runSearch()}
          disabled={isPending || !query.trim()}
        >
          Search
        </Button>
      </Box>

      {/* Results */}
      {isPending && <LoadingSpinner message="Searching…" />}
      {isError && (
        <Typography color="error">Search failed: {(error as Error).message}</Typography>
      )}
      {data && (
        <Box>
          <Typography variant="body2" color="text.secondary" mb={2}>
            {data.total} result{data.total !== 1 ? 's' : ''} — {data.mode} search
          </Typography>

          {data.results.length === 0 ? (
            <Typography color="text.secondary">No results found for "{query}"</Typography>
          ) : (
            data.results.map((result: SearchResult) => (
              <Card key={result.chunk_id} variant="outlined" sx={{ mb: 2 }}>
                <CardContent>
                  <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={1}>
                    <Typography variant="subtitle2" fontWeight={600}>
                      {result.filename}
                    </Typography>
                    <Chip label={`Score: ${result.score.toFixed(3)}`} size="small" />
                  </Box>

                  {result.section && (
                    <Typography variant="caption" color="text.secondary" display="block" mb={1}>
                      Section: {result.section}
                    </Typography>
                  )}

                  <Divider sx={{ my: 1 }} />

                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                    {result.content}
                  </Typography>
                </CardContent>
              </Card>
            ))
          )}
        </Box>
      )}
    </Box>
  );
}
