import Grid from '@mui/material/Grid2';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Box from '@mui/material/Box';
import ChatIcon from '@mui/icons-material/Chat';
import SearchIcon from '@mui/icons-material/Search';
import FolderIcon from '@mui/icons-material/Folder';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import { useNavigate } from 'react-router-dom';
import { useHealth } from '@/hooks/useHealth';
import { ROUTES } from '@/utils/constants';

const QUICK_ACTIONS = [
  {
    title: 'Ask a Question',
    description: 'Use the RAG pipeline to ask questions grounded in your indexed documents.',
    icon: <ChatIcon fontSize="large" color="primary" />,
    path: ROUTES.CHAT,
    label: 'Go to Chat',
  },
  {
    title: 'Search Documents',
    description: 'Run keyword, vector, or hybrid search directly against the index.',
    icon: <SearchIcon fontSize="large" color="secondary" />,
    path: ROUTES.SEARCH,
    label: 'Go to Search',
  },
  {
    title: 'Manage Documents',
    description: 'View indexed documents, trigger ingestion, and monitor processing status.',
    icon: <FolderIcon fontSize="large" sx={{ color: 'warning.main' }} />,
    path: ROUTES.DOCUMENTS,
    label: 'View Documents',
  },
] as const;

export default function Home() {
  const navigate = useNavigate();
  const { data: health, isLoading } = useHealth();

  return (
    <Box>
      {/* Header */}
      <Box mb={4}>
        <Typography variant="h4" gutterBottom fontWeight={700}>
          Welcome to Radia AI
        </Typography>
        <Typography variant="body1" color="text.secondary" maxWidth={600}>
          Enterprise engineering knowledge assistant. Ask questions about your requirements,
          search indexed documents, and get grounded answers from Azure AI.
        </Typography>
      </Box>

      {/* System status */}
      <Box mb={4} display="flex" alignItems="center" gap={1}>
        <Typography variant="subtitle2" color="text.secondary">
          System Status:
        </Typography>
        {isLoading ? (
          <Chip label="Checking..." size="small" />
        ) : (
          <Chip
            icon={<CheckCircleIcon />}
            label={`API ${health?.status ?? 'unknown'} — v${health?.version ?? '—'}`}
            color={health?.status === 'ok' ? 'success' : 'warning'}
            size="small"
            variant="outlined"
          />
        )}
      </Box>

      {/* Quick action cards */}
      <Grid container spacing={3}>
        {QUICK_ACTIONS.map(({ title, description, icon, path, label }) => (
          <Grid key={path} size={{ xs: 12, md: 4 }}>
            <Card
              sx={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                cursor: 'pointer',
                transition: 'transform 0.15s, box-shadow 0.15s',
                '&:hover': {
                  transform: 'translateY(-2px)',
                  boxShadow: 4,
                },
              }}
              onClick={() => navigate(path)}
            >
              <CardContent sx={{ flexGrow: 1 }}>
                <Box mb={2}>{icon}</Box>
                <Typography variant="h6" gutterBottom fontWeight={600}>
                  {title}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {description}
                </Typography>
              </CardContent>
              <Box px={2} pb={2}>
                <Button variant="outlined" size="small" onClick={() => navigate(path)}>
                  {label}
                </Button>
              </Box>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Dependency health */}
      {health?.dependencies && health.dependencies.length > 0 && (
        <Box mt={4}>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>
            Dependency Health
          </Typography>
          <Box display="flex" gap={1} flexWrap="wrap">
            {health.dependencies.map((dep) => (
              <Chip
                key={dep.name}
                label={`${dep.name}: ${dep.status}`}
                color={dep.status === 'ok' ? 'success' : dep.status === 'degraded' ? 'warning' : 'error'}
                size="small"
                variant="outlined"
              />
            ))}
          </Box>
        </Box>
      )}
    </Box>
  );
}
