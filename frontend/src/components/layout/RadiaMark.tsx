import Box from '@mui/material/Box';

interface RadiaMarkProps {
  size?: number;
}

export function RadiaMark({ size = 36 }: RadiaMarkProps) {
  return (
    <Box
      sx={{
        position: 'relative',
        width: size,
        height: size,
        borderRadius: '28% 50% 38% 50%',
        background: 'linear-gradient(150deg, #ff6b6b 0%, #e11d48 52%, #7f1d1d 100%)',
        boxShadow: '0 14px 30px rgba(225, 29, 72, 0.28)',
        overflow: 'hidden',
        flexShrink: 0,
      }}
      aria-hidden="true"
    >
      <Box
        sx={{
          position: 'absolute',
          inset: '18% 20% auto auto',
          width: '54%',
          height: '54%',
          borderTop: '3px solid rgba(255,255,255,0.94)',
          borderRight: '3px solid rgba(255,255,255,0.94)',
          borderRadius: '0 80% 0 0',
          transform: 'rotate(18deg)',
        }}
      />
      <Box
        sx={{
          position: 'absolute',
          left: '28%',
          top: '22%',
          width: '14%',
          height: '58%',
          borderRadius: 999,
          bgcolor: 'rgba(255,255,255,0.96)',
          transform: 'rotate(18deg)',
        }}
      />
      <Box
        sx={{
          position: 'absolute',
          right: '-14%',
          bottom: '-14%',
          width: '60%',
          height: '60%',
          borderRadius: '50%',
          background: 'rgba(255,255,255,0.16)',
        }}
      />
    </Box>
  );
}
