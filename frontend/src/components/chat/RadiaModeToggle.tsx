import FormControlLabel from '@mui/material/FormControlLabel';
import Switch from '@mui/material/Switch';

interface RadiaModeToggleProps {
  checked: boolean;
  disabled: boolean;
  onChange: (checked: boolean) => void;
}

export function RadiaModeToggle({ checked, disabled, onChange }: RadiaModeToggleProps) {
  return (
    <FormControlLabel
      label="Radia AI"
      labelPlacement="start"
      sx={{ m: 0, gap: 0.5, flexShrink: 0 }}
      slotProps={{ typography: { variant: 'body2', fontWeight: 600 } }}
      control={
        <Switch
          size="small"
          checked={checked}
          disabled={disabled}
          onChange={(_, value) => onChange(value)}
          inputProps={{ role: 'switch', 'aria-label': 'Radia AI mode' }}
        />
      }
    />
  );
}
