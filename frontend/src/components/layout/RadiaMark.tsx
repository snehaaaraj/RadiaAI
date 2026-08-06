const OUTER_SPOKES = Array.from({ length: 24 }, (_, index) => index * 15);
const INNER_SPOKES = Array.from({ length: 24 }, (_, index) => index * 15 + 7.5);
const LOGO_COLOR = '#2F4352';

interface RadiaMarkProps {
  size?: number;
}

export function RadiaMark({ size = 36 }: RadiaMarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 128 128"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      style={{ display: 'block', flexShrink: 0 }}
    >
      <circle cx="64" cy="64" r="21" fill="white" />

      {OUTER_SPOKES.map((angle) => (
        <rect
          key={`outer-${angle}`}
          x="60"
          y="6"
          width="8"
          height="18"
          rx="1.5"
          fill={LOGO_COLOR}
          transform={`rotate(${angle} 64 64)`}
        />
      ))}

      {INNER_SPOKES.map((angle) => (
        <rect
          key={`inner-${angle}`}
          x="59.5"
          y="30"
          width="9"
          height="15"
          rx="1.5"
          fill={LOGO_COLOR}
          transform={`rotate(${angle} 64 64)`}
        />
      ))}
    </svg>
  );
}
