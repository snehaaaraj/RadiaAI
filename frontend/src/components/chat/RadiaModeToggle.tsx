import Box from '@mui/material/Box';
import FormControlLabel from '@mui/material/FormControlLabel';
import Switch from '@mui/material/Switch';
import Typography from '@mui/material/Typography';
import Tooltip from '@mui/material/Tooltip';
import { alpha } from '@mui/material/styles';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';

interface RadiaModeToggleProps {
  checked: boolean;
  disabled: boolean;
  onChange: (checked: boolean) => void;
}

export function RadiaModeToggle({ checked, disabled, onChange }: RadiaModeToggleProps) {
  return (
    <Tooltip
      title={checked
        ? 'Turn it off to switch back to Radia Chatbot'
        : 'Turn it on to connect to Jama contents'}
      placement="bottom"
      describeChild
      arrow
    >
    <FormControlLabel
      label={
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
          <Box
            sx={{
              display: 'grid',
              placeItems: 'center',
              width: 26,
              height: 26,
              borderRadius: '50%',
              bgcolor: (theme) => alpha(theme.palette.primary.main, checked ? 0.15 : 0.07),
              color: checked ? 'primary.main' : 'text.secondary',
            }}
          >
            <AutoAwesomeRoundedIcon sx={{ fontSize: 16 }} />
          </Box>
          <Typography component="span" variant="body2" fontWeight={700}>
            Radia AI
          </Typography>
          <Typography
            component="span"
            variant="caption"
            sx={{
              color: checked ? 'primary.main' : 'text.secondary',
              fontSize: '0.625rem',
              fontWeight: 800,
              letterSpacing: '0.06em',
            }}
          >
            {checked ? 'ON' : 'OFF'}
          </Typography>
        </Box>
      }
      labelPlacement="start"
      disableTypography
      sx={(theme) => ({
        m: 0,
        gap: 0.75,
        flexShrink: 0,
        pl: 0.75,
        pr: 0.5,
        py: 0.5,
        borderRadius: 999,
        border: '1px solid',
        borderColor: alpha(theme.palette.primary.main, checked ? 0.3 : 0.12),
        bgcolor: 'background.paper',
        color: 'text.primary',
        backgroundImage: `linear-gradient(120deg, ${alpha(theme.palette.primary.main, checked ? 0.1 : 0.025)}, ${alpha(theme.palette.secondary.main, checked ? 0.08 : 0.025)})`,
        boxShadow: checked ? `0 3px 14px ${alpha(theme.palette.primary.main, 0.13)}` : 'none',
        opacity: disabled ? 0.6 : 1,
        transition: 'border-color 180ms ease, box-shadow 180ms ease',
        '&:hover': disabled ? {} : {
          borderColor: alpha(theme.palette.primary.main, 0.45),
          boxShadow: `0 3px 16px ${alpha(theme.palette.primary.main, 0.16)}`,
        },
        '&:focus-within': {
          outline: `2px solid ${theme.palette.primary.main}`,
          outlineOffset: 3,
        },
        '@media (prefers-reduced-motion: reduce)': { transition: 'none' },
      })}
      control={
        <Switch
          size="small"
          checked={checked}
          disabled={disabled}
          onChange={(_, value) => onChange(value)}
          inputProps={{ role: 'switch', 'aria-label': 'Radia AI mode' }}
          sx={{
            width: 42,
            height: 26,
            p: 0,
            '& .MuiSwitch-switchBase': {
              p: '3px',
              '&.Mui-checked': {
                transform: 'translateX(16px)',
                color: 'common.white',
                '& + .MuiSwitch-track': { opacity: 1, bgcolor: 'primary.main' },
              },
            },
            '& .MuiSwitch-thumb': {
              width: 20,
              height: 20,
              boxShadow: '0 1px 4px rgba(0, 0, 0, 0.18)',
            },
            '& .MuiSwitch-track': {
              borderRadius: 999,
              opacity: 1,
              bgcolor: 'action.disabledBackground',
            },
            '@media (prefers-reduced-motion: reduce)': {
              '& .MuiSwitch-switchBase, & .MuiSwitch-track': { transition: 'none' },
            },
          }}
        />
      }
    />
    </Tooltip>
  );
}
