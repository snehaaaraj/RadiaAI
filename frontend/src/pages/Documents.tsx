import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Paper from '@mui/material/Paper';
import Chip from '@mui/material/Chip';
import { useDocuments } from '@/hooks/useDocuments';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import type { DocumentStatus } from '@/types/api';
import { getApiErrorMessage } from '@/utils/apiErrorMessage';

const STATUS_COLOR: Record<DocumentStatus, 'default' | 'warning' | 'success' | 'error'> = {
  pending: 'default',
  processing: 'warning',
  indexed: 'success',
  failed: 'error',
};

export default function Documents() {
  const { data, isLoading, isError, error } = useDocuments();

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} mb={3}>
        Documents
      </Typography>

      {isLoading && <LoadingSpinner message="Loading documents…" />}

      {isError && (
        <Typography color="error">Failed to load documents: {getApiErrorMessage(error)}</Typography>
      )}

      {data && (
        <>
          <Typography variant="body2" color="text.secondary" mb={2}>
            {data.total} document{data.total !== 1 ? 's' : ''} indexed
          </Typography>

          {data.data.length === 0 ? (
            <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
              <Typography color="text.secondary">
                No documents indexed yet. Use the ingestion pipeline to add documents.
              </Typography>
            </Paper>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Filename</TableCell>
                    <TableCell>Source</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell align="right">Chunks</TableCell>
                    <TableCell>Ingested</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.data.map((doc) => (
                    <TableRow key={doc.document_id} hover>
                      <TableCell>{doc.filename}</TableCell>
                      <TableCell>{doc.metadata.source}</TableCell>
                      <TableCell>
                        <Chip
                          label={doc.status}
                          color={STATUS_COLOR[doc.status]}
                          size="small"
                        />
                      </TableCell>
                      <TableCell align="right">{doc.chunk_count}</TableCell>
                      <TableCell>
                        {doc.ingested_at
                          ? new Date(doc.ingested_at).toLocaleDateString()
                          : '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </>
      )}
    </Box>
  );
}
