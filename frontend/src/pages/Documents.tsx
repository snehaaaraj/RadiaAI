import { useMemo, useState } from 'react';
import Accordion from '@mui/material/Accordion';
import AccordionDetails from '@mui/material/AccordionDetails';
import AccordionSummary from '@mui/material/AccordionSummary';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import MenuItem from '@mui/material/MenuItem';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TablePagination from '@mui/material/TablePagination';
import TableRow from '@mui/material/TableRow';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { useDeleteDocument, useDocument, useDocuments } from '@/hooks/useDocuments';
import { useCurrentUser } from '@/hooks/useCurrentUser';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import type { DocumentStatus } from '@/types/api';
import { getApiErrorMessage } from '@/utils/apiErrorMessage';

const STATUS_COLOR: Record<DocumentStatus, 'default' | 'warning' | 'success' | 'error'> = {
  pending: 'default',
  processing: 'warning',
  indexed: 'success',
  failed: 'error',
};

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

export default function Documents() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [source, setSource] = useState('');
  const [query, setQuery] = useState('');
  const [sortBy, setSortBy] = useState<'filename' | 'source' | 'chunk_count' | 'ingested_at'>(
    'filename'
  );
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const listParams = useMemo(
    () => ({ page, pageSize, source, query, sortBy, sortOrder }),
    [page, pageSize, source, query, sortBy, sortOrder]
  );
  const { data, isLoading, isError, error, isPlaceholderData } = useDocuments(listParams);
  const documentQuery = useDocument(selectedDocumentId);
  const deleteMutation = useDeleteDocument();
  const { data: currentUser } = useCurrentUser();
  const canManageDocuments = currentUser?.can_manage_documents ?? false;

  const handleDelete = () => {
    if (!selectedDocumentId) return;
    deleteMutation.mutate(selectedDocumentId, {
      onSuccess: () => {
        setConfirmDelete(false);
        setSelectedDocumentId(null);
      },
    });
  };

  const resetPage = () => setPage(1);

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} mb={3}>
        Documents
      </Typography>

      <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} mb={2}>
        <TextField
          size="small"
          label="Search filename"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            resetPage();
          }}
          sx={{ minWidth: 240 }}
        />
        <TextField
          size="small"
          label="Source"
          value={source}
          onChange={(event) => {
            setSource(event.target.value);
            resetPage();
          }}
          sx={{ minWidth: 180 }}
        />
        <TextField
          select
          size="small"
          label="Sort by"
          value={sortBy}
          onChange={(event) => {
            setSortBy(event.target.value as typeof sortBy);
            resetPage();
          }}
          sx={{ minWidth: 160 }}
        >
          <MenuItem value="filename">Filename</MenuItem>
          <MenuItem value="source">Source</MenuItem>
          <MenuItem value="chunk_count">Chunk count</MenuItem>
          <MenuItem value="ingested_at">Ingested date</MenuItem>
        </TextField>
        <TextField
          select
          size="small"
          label="Order"
          value={sortOrder}
          onChange={(event) => {
            setSortOrder(event.target.value as typeof sortOrder);
            resetPage();
          }}
          sx={{ minWidth: 120 }}
        >
          <MenuItem value="asc">Ascending</MenuItem>
          <MenuItem value="desc">Descending</MenuItem>
        </TextField>
      </Stack>

      {isLoading && <LoadingSpinner message="Loading documents…" />}

      {isError && (
        <Alert severity="error">Failed to load documents: {getApiErrorMessage(error)}</Alert>
      )}

      {data && (
        <>
          <Typography variant="body2" color="text.secondary" mb={2}>
            {data.total} document{data.total !== 1 ? 's' : ''} found
          </Typography>

          {data.data.length === 0 ? (
            <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
              <Typography color="text.secondary">
                No matching indexed documents. Use the ingestion pipeline to add documents.
              </Typography>
            </Paper>
          ) : (
            <>
              <TableContainer component={Paper} variant="outlined">
                <Table size="small" aria-label="Indexed documents">
                  <TableHead>
                    <TableRow>
                      <TableCell>Filename</TableCell>
                      <TableCell>Source</TableCell>
                      <TableCell>Type</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell align="right">Chunks</TableCell>
                      <TableCell>Ingested</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {data.data.map((doc) => (
                      <TableRow key={doc.document_id} hover>
                        <TableCell>
                          <Button
                            size="small"
                            sx={{ px: 0, textTransform: 'none', textAlign: 'left' }}
                            onClick={() => setSelectedDocumentId(doc.document_id)}
                          >
                            {doc.filename}
                          </Button>
                        </TableCell>
                        <TableCell>{doc.metadata.source}</TableCell>
                        <TableCell>{doc.metadata.document_type || '-'}</TableCell>
                        <TableCell>
                          <Chip
                            label={doc.status}
                            color={STATUS_COLOR[doc.status]}
                            size="small"
                          />
                        </TableCell>
                        <TableCell align="right">{doc.chunk_count}</TableCell>
                        <TableCell>
                          {doc.ingested_at ? new Date(doc.ingested_at).toLocaleDateString() : '-'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
              <TablePagination
                component="div"
                count={data.total}
                page={page - 1}
                rowsPerPage={pageSize}
                rowsPerPageOptions={PAGE_SIZE_OPTIONS}
                onPageChange={(_, nextPage) => setPage(nextPage + 1)}
                onRowsPerPageChange={(event) => {
                  setPageSize(Number(event.target.value));
                  resetPage();
                }}
                disabled={isPlaceholderData}
              />
            </>
          )}
        </>
      )}

      <Dialog
        open={selectedDocumentId !== null}
        onClose={() => setSelectedDocumentId(null)}
        fullWidth
        maxWidth="md"
      >
        <DialogTitle>Document details</DialogTitle>
        <DialogContent dividers>
          {documentQuery.isLoading && <LoadingSpinner message="Loading document details…" />}
          {documentQuery.isError && (
            <Alert severity="error">
              Failed to load document details: {getApiErrorMessage(documentQuery.error)}
            </Alert>
          )}
          {documentQuery.data && (
            <Stack spacing={2}>
              <Box>
                <Typography variant="h6">{documentQuery.data.filename}</Typography>
                <Typography variant="caption" color="text.secondary" sx={{ overflowWrap: 'anywhere' }}>
                  Document ID: {documentQuery.data.document_id}
                </Typography>
              </Box>
              <Stack direction="row" spacing={1} flexWrap="wrap">
                <Chip label={`Source: ${documentQuery.data.metadata.source}`} size="small" />
                <Chip
                  label={`Type: ${documentQuery.data.metadata.document_type || 'Not set'}`}
                  size="small"
                />
                <Chip label={`Status: ${documentQuery.data.status}`} size="small" />
                <Chip label={`${documentQuery.data.chunk_count} chunks`} size="small" />
                {documentQuery.data.metadata.author && (
                  <Chip label={`Author: ${documentQuery.data.metadata.author}`} size="small" />
                )}
                {documentQuery.data.metadata.version && (
                  <Chip label={`Version: ${documentQuery.data.metadata.version}`} size="small" />
                )}
              </Stack>
              <Typography variant="subtitle1" fontWeight={600}>
                Indexed chunks
              </Typography>
              {documentQuery.data.chunks.length === 0 ? (
                <Alert severity="info">No chunks are currently indexed for this document.</Alert>
              ) : (
                documentQuery.data.chunks.map((chunk) => (
                  <Accordion key={chunk.chunk_id} disableGutters>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="body2">
                        Chunk {chunk.chunk_index + 1}
                        {chunk.page_number ? ` · Page ${chunk.page_number}` : ''}
                        {chunk.section ? ` · Section ${chunk.section}` : ''}
                      </Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
                        {chunk.content}
                      </Typography>
                    </AccordionDetails>
                  </Accordion>
                ))
              )}
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          {canManageDocuments && (
            <Button
              color="error"
              startIcon={<DeleteOutlineIcon />}
              onClick={() => setConfirmDelete(true)}
              disabled={!documentQuery.data || deleteMutation.isPending}
            >
              Delete indexed copy
            </Button>
          )}
          <Button onClick={() => setSelectedDocumentId(null)}>Close</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={confirmDelete} onClose={() => setConfirmDelete(false)}>
        <DialogTitle>Delete indexed document?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            This removes the document and its chunks from the search index. The source file in Blob
            Storage or SharePoint will not be changed.
          </DialogContentText>
          {deleteMutation.isError && (
            <Alert severity="error" sx={{ mt: 2 }}>
              Delete failed: {getApiErrorMessage(deleteMutation.error)}
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDelete(false)} disabled={deleteMutation.isPending}>
            Cancel
          </Button>
          <Button
            color="error"
            variant="contained"
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
          >
            {deleteMutation.isPending ? <CircularProgress size={18} color="inherit" /> : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
