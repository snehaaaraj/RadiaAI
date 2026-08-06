import Box from '@mui/material/Box';
import { useTheme } from '@mui/material/styles';

const lightLogoUrl = new URL('../../assets/radia-circle-white background.png', import.meta.url).href;
const darkLogoUrl = new URL('../../assets/radia-circle-white lines.jpg', import.meta.url).href;

interface RadiaMarkProps {
  size?: number;
}

export function RadiaMark({ size = 36 }: RadiaMarkProps) {
  const theme = useTheme();
  const logoSrc = theme.palette.mode === 'dark' ? darkLogoUrl : lightLogoUrl;

  return (
    <Box
      component="img"
      src={logoSrc}
      alt="Radia logo"
      sx={{
        width: size,
        height: size,
        objectFit: 'contain',
        display: 'block',
        flexShrink: 0,
      }}
    />
  );
}
