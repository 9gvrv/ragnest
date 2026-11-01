type IconProps = { className?: string };

const base = {
  "aria-hidden": true,
  focusable: false,
  fill: "none",
  viewBox: "0 0 16 16",
  stroke: "currentColor",
  strokeWidth: 1.5,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export function PanelLeftIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <rect x="2" y="2.75" width="12" height="10.5" rx="1.75" />
      <path d="M6 2.75v10.5" />
    </svg>
  );
}

export function MenuIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M2.5 4.5h11M2.5 8h11M2.5 11.5h11" />
    </svg>
  );
}

export function XIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="m4 4 8 8M12 4l-8 8" />
    </svg>
  );
}

export function ChevronDownIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="m4 6 4 4 4-4" />
    </svg>
  );
}

export function ArrowLeftIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M12.5 8h-9M7 3.5 2.5 8 7 12.5" />
    </svg>
  );
}

export function UploadIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M8 10.5V3M5 6l3-3 3 3" />
      <path d="M2.75 10.5v1.25a1.5 1.5 0 0 0 1.5 1.5h7.5a1.5 1.5 0 0 0 1.5-1.5V10.5" />
    </svg>
  );
}

export function TrashIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.6 8.2a1.2 1.2 0 0 0 1.2 1.1h3.4a1.2 1.2 0 0 0 1.2-1.1l.6-8.2" />
    </svg>
  );
}

export function PlusIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M8 3v10M3 8h10" />
    </svg>
  );
}

export function ArrowUpIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M8 13V3M3.5 7.5 8 3l4.5 4.5" />
    </svg>
  );
}

export function MoreHorizontalIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <circle cx="3.5" cy="8" r="0.9" fill="currentColor" stroke="none" />
      <circle cx="8" cy="8" r="0.9" fill="currentColor" stroke="none" />
      <circle cx="12.5" cy="8" r="0.9" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function UserPlusIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <circle cx="6.25" cy="5.25" r="2.5" />
      <path d="M2.5 13.25c0-2 1.7-3.5 3.75-3.5 1.1 0 2.1.45 2.8 1.15" />
      <path d="M11.75 9.5v3.5M10 11.25h3.5" />
    </svg>
  );
}

export function UserMinusIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <circle cx="6.25" cy="5.25" r="2.5" />
      <path d="M2.5 13.25c0-2 1.7-3.5 3.75-3.5 1.1 0 2.1.45 2.8 1.15" />
      <path d="M10 11.25h3.5" />
    </svg>
  );
}

export function MessageIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M2.75 3.75h10.5v7.5H8l-3 2.25V11.25H2.75z" />
    </svg>
  );
}
