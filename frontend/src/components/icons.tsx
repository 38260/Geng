import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function base({ size = 18, ...props }: IconProps) {
  return {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.9,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    ...props,
  };
}

export const HomeIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-4v-6h-6v6H5a1 1 0 0 1-1-1z" />
  </svg>
);

export const LibraryIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <rect x="4" y="4" width="7" height="16" rx="2" />
    <path d="M14 8h6M14 12h6M14 16h4" />
  </svg>
);

export const TrendIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M4 19V5" />
    <path d="M4 19h16" />
    <path d="M7.5 15.5 11 11l3 2.5L19 7" />
  </svg>
);

export const BookmarkIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M6 4h12v16l-6-4.5L6 20z" />
  </svg>
);

export const GearIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <circle cx="12" cy="12" r="3.2" />
    <path d="M12 3.5v2M12 18.5v2M3.5 12h2M18.5 12h2M6 6l1.5 1.5M16.5 16.5 18 18M18 6l-1.5 1.5M7.5 16.5 6 18" />
  </svg>
);

export const SearchIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <circle cx="11" cy="11" r="6.5" />
    <path d="m16 16 4 4" />
  </svg>
);

export const CalendarIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <rect x="3.5" y="5" width="17" height="15" rx="3" />
    <path d="M8 3.5v4M16 3.5v4M3.5 10h17" />
  </svg>
);

export const ArrowRightIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M5 12h13M13 7l5 5-5 5" />
  </svg>
);

export const ArrowLeftIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M19 12H6M11 7l-5 5 5 5" />
  </svg>
);

export const PlayIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <circle cx="12" cy="12" r="9" />
    <path d="M10 8.8 15.5 12 10 15.2z" fill="currentColor" stroke="none" />
  </svg>
);

export const UsersIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <circle cx="9" cy="8" r="3.2" />
    <path d="M3.5 19c.6-3 2.8-4.6 5.5-4.6S14 16 14.6 19" />
    <path d="M16 6.2a3 3 0 0 1 0 5.6M17.5 19c-.2-1.4-.7-2.5-1.5-3.4" />
  </svg>
);

export const CommentIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M4.5 6.5h15v10h-9l-4 3v-3h-2z" />
    <path d="M8.5 11h7M8.5 14h4" />
  </svg>
);

export const DanmakuIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <rect x="3" y="6" width="18" height="12" rx="3" />
    <path d="M6.5 10.5h5M6.5 13.5h8M15 10.5h2.5" />
  </svg>
);

export const CheckIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <circle cx="12" cy="12" r="9" />
    <path d="m8 12.4 2.6 2.6L16 9.6" />
  </svg>
);

export const StarIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="m12 4 2.4 4.9 5.4.8-3.9 3.8.9 5.4-4.8-2.5-4.8 2.5.9-5.4L4.2 9.7l5.4-.8z" />
  </svg>
);

export const FireIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M13 3s.8 3.2-1.4 5.3C9.2 10.6 7 12 7 15a5.5 5.5 0 0 0 11 0c0-2.6-1.4-4-2.6-5.6C14 7.4 13 5.2 13 3Z" />
  </svg>
);

export const RocketIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M13.5 4.5C17 6 19 9.5 19 13.5L14.5 18 9 12.5 13.5 4.5Z" />
    <path d="M9 12.5 5.5 13l-.5 3.5M13.5 18l.5 3.5 3.5-.5" />
    <circle cx="14.2" cy="9.8" r="1.4" />
  </svg>
);

export const WaveIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M3 15c2.2-3 4.4-3 6.6 0s4.4 3 6.6 0 3.6-2.4 4.8-1" />
    <path d="M3 9.5c2.2-3 4.4-3 6.6 0s4.4 3 6.6 0" />
  </svg>
);

export const RefreshIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M20 11a8 8 0 1 0-2.3 6.2" />
    <path d="M20 5.5V11h-5.5" />
  </svg>
);

export const EyeIcon = ({ open = true, ...p }: IconProps & { open?: boolean }) => (
  <svg {...base(p)}>
    <path d="M2.5 12S6 6.5 12 6.5 21.5 12 21.5 12 18 17.5 12 17.5 2.5 12 2.5 12Z" />
    {open ? <circle cx="12" cy="12" r="2.6" /> : <path d="M4 19 20 5" />}
  </svg>
);

export const LinkIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M10 13.5a3.5 3.5 0 0 0 5 0l2.5-2.5a3.5 3.5 0 0 0-5-5L11 7.5" />
    <path d="M14 10.5a3.5 3.5 0 0 0-5 0L6.5 13a3.5 3.5 0 0 0 5 5l1.5-1.5" />
  </svg>
);
