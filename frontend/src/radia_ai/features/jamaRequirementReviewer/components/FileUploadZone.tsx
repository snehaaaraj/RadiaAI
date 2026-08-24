import { useRef, useState, useCallback } from 'react';
import CloseIcon from '@mui/icons-material/Close';
import UploadFileOutlinedIcon from '@mui/icons-material/UploadFileOutlined';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import Typography from '@mui/material/Typography';
import * as pdfjsLib from 'pdfjs-dist';
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { cleanExtractedText } from './fileUploadTextCleaner';

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

interface FileUploadZoneProps {
  /** Comma-separated MIME types or extensions, e.g. ".txt,.json,.csv" */
  accept: string;
  /** Hint shown inside the drop zone */
  label: string;
  /** Called with the extracted file text content and the filename */
  onFileContent: (content: string, filename: string) => void;
  /** Filename currently loaded — pass to show the "loaded" state */
  filename?: string;
  onClear?: () => void;
}


async function extractPdfText(arrayBuffer: ArrayBuffer) {
  const document = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
  const pageTexts: string[] = [];

  for (let pageNumber = 1; pageNumber <= document.numPages; pageNumber += 1) {
    const page = await document.getPage(pageNumber);
    const textContent = await page.getTextContent();

    // Preserve line breaks by checking the hasEOL flag on each item
    let pageText = '';
    for (const item of textContent.items) {
      if (!('str' in item)) continue;
      pageText += item.str;
      if ((item as { hasEOL?: boolean }).hasEOL) pageText += '\n';
      else pageText += ' ';
    }
    const trimmed = pageText.trim();
    if (trimmed) pageTexts.push(trimmed);
  }

  const fullText = pageTexts.join('\n\n');
  return cleanExtractedText(fullText);
}

export function FileUploadZone({ accept, label, onFileContent, filename, onClear }: FileUploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [readError, setReadError] = useState('');

  const readFile = useCallback(
    async (file: File) => {
      setReadError('');
      const lowerName = file.name.toLowerCase();
      const isPdf = lowerName.endsWith('.pdf') || file.type === 'application/pdf';

      try {
        if (isPdf) {
          const arrayBuffer = await file.arrayBuffer();
          const content = await extractPdfText(arrayBuffer);
          onFileContent(content, file.name);
          return;
        }

        const content = await file.text();
        onFileContent(cleanExtractedText(content), file.name);
      } catch {
        setReadError('Failed to read file.');
      }
    },
    [onFileContent]
  );

  const handleDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setIsDragOver(false);
      const file = event.dataTransfer.files[0];
      if (file) readFile(file);
    },
    [readFile]
  );

  const handleFileChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (file) readFile(file);
      // reset so same file can be re-selected
      event.target.value = '';
    },
    [readFile]
  );

  if (filename) {
    return (
      <Box
        display="flex"
        alignItems="center"
        gap={1}
        px={2}
        py={1.5}
        sx={{
          border: '1px solid',
          borderColor: 'success.main',
          borderRadius: 1,
          bgcolor: 'success.50',
        }}
      >
        <UploadFileOutlinedIcon fontSize="small" color="success" />
        <Typography variant="body2" sx={{ flexGrow: 1, wordBreak: 'break-all' }}>
          {filename}
        </Typography>
        <IconButton
          size="small"
          aria-label="remove file"
          onClick={() => {
            setReadError('');
            onClear?.();
          }}
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>
    );
  }

  return (
    <Box>
      <Box
        role="button"
        tabIndex={0}
        aria-label={label}
        onDragOver={(event) => {
          event.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') inputRef.current?.click();
        }}
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 1,
          py: 4,
          border: '2px dashed',
          borderColor: isDragOver ? 'primary.main' : 'divider',
          borderRadius: 1,
          bgcolor: isDragOver ? 'primary.50' : 'background.default',
          cursor: 'pointer',
          transition: 'border-color 0.15s, background-color 0.15s',
          '&:hover': { borderColor: 'primary.light', bgcolor: 'action.hover' },
          '&:focus-visible': { outline: '2px solid', outlineColor: 'primary.main' },
        }}
      >
        <UploadFileOutlinedIcon color="action" />
        <Typography variant="body2" color="text.secondary" align="center">
          {label}
        </Typography>
        <Typography variant="caption" color="text.disabled">
          Drag &amp; drop or click to browse
        </Typography>
      </Box>

      <input
        ref={inputRef}
        type="file"
        accept={accept}
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />

      {readError && (
        <Alert severity="error" sx={{ mt: 1 }}>
          {readError}
        </Alert>
      )}
    </Box>
  );
}
