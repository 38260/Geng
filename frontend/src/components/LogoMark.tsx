/**
 * 「赶梗潮」标识。
 *
 * 参考图里的 Logo 是一只蓝色小幽灵（B 站氛围的吉祥物）。这里用内联 SVG 画出来，
 * 不依赖外部图片资源，也不会出现 AI 科技感元素。
 */
export function LogoMark({ size = 34, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      className={className}
      role="img"
      aria-label="赶梗潮 logo"
    >
      <defs>
        <linearGradient id="geng-body" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#6FA8FF" />
          <stop offset="100%" stopColor="#3E7BF0" />
        </linearGradient>
      </defs>
      <path
        d="M24 4c9.4 0 16 6.6 16 15.6v11.2c0 2.4-.3 4.4-1 6.2l-3.2-2.2-2.8 3.2-3.1-2.4-2.9 3.2-3-2.6-3 2.6-2.9-3.2-3.1 2.4-2.8-3.2L5 37c-.7-1.8-1-3.8-1-6.2V19.6C4 10.6 14.6 4 24 4Z"
        fill="url(#geng-body)"
        stroke="#2450A8"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <ellipse cx="18" cy="20" rx="2.6" ry="3.2" fill="#fff" />
      <ellipse cx="30" cy="20" rx="2.6" ry="3.2" fill="#fff" />
      <circle cx="18.4" cy="20.8" r="1.3" fill="#1B2A44" />
      <circle cx="30.4" cy="20.8" r="1.3" fill="#1B2A44" />
      <path d="M21 26c1.8 1.6 4.2 1.6 6 0" stroke="#1B2A44" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      <ellipse cx="13.4" cy="25.4" rx="2.4" ry="1.5" fill="#FF9E93" opacity="0.75" />
      <ellipse cx="34.6" cy="25.4" rx="2.4" ry="1.5" fill="#FF9E93" opacity="0.75" />
    </svg>
  );
}
