import React from 'react'

interface IconProps {
  size?: number
  className?: string
  style?: React.CSSProperties
}

const base = (size = 18, className = '', style?: React.CSSProperties) => ({
  width: size,
  height: size,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  className,
  style,
  'aria-hidden': true,
})

export const IconDashboard = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}>
    <rect x="3" y="3" width="7" height="9" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" />
    <rect x="14" y="12" width="7" height="9" rx="1.5" /><rect x="3" y="16" width="7" height="5" rx="1.5" />
  </svg>
)
export const IconRoles = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}>
    <path d="M8 8h11" /><path d="M8 12h11" /><path d="M8 16h11" />
    <circle cx="4.5" cy="8" r="1.2" fill="currentColor" stroke="none" />
    <circle cx="4.5" cy="12" r="1.2" fill="currentColor" stroke="none" />
    <circle cx="4.5" cy="16" r="1.2" fill="currentColor" stroke="none" />
  </svg>
)
export const IconLearning = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}>
    <path d="M12 3l8 4-8 4-8-4 8-4z" /><path d="M4 11v5c0 1.5 3.6 3 8 3s8-1.5 8-3v-5" /><path d="M20 11v5" />
  </svg>
)
export const IconAssessment = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}>
    <path d="M9 3h6a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" />
    <path d="M12 7v4" /><circle cx="12" cy="15" r=".6" fill="currentColor" />
  </svg>
)
export const IconUniversity = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}>
    <path d="M3 9l9-5 9 5-9 5-9-5z" /><path d="M6 11v5c0 1 2.7 2 6 2 3.3 0 6-1 6-2v-5" />
    <path d="M21 9v6" />
  </svg>
)
export const IconCheck = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}>
    <path d="M20 6L9 17l-5-5" />
  </svg>
)
export const IconVerified = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}>
    <path d="M12 2l2.1 1.6 2.6-.3 1 2.4 2.4 1-.3 2.6L21.4 12l-1.6 2.1.3 2.6-2.4 1-1 2.4-2.6-.3L12 22l-2.1-1.6-2.6.3-1-2.4-2.4-1 .3-2.6L2.6 12 4.2 9.9l-.3-2.6 2.4-1 1-2.4 2.6.3L12 2z" />
    <path d="M9 12l2 2 4-4" />
  </svg>
)
export const IconPlus = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}><path d="M12 5v14M5 12h14" /></svg>
)
export const IconEdit = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}>
    <path d="M17 3a2.8 2.8 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
  </svg>
)
export const IconTrash = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}>
    <path d="M3 6h18" /><path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2" />
    <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
  </svg>
)
export const IconUpload = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <path d="M17 8l-5-5-5 5" /><path d="M12 3v12" />
  </svg>
)
export const IconSend = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}>
    <path d="M22 2L11 13" /><path d="M22 2l-7 20-4-9-9-4 20-7z" />
  </svg>
)
export const IconFlag = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}>
    <path d="M4 22V4" /><path d="M4 4c5-3 6 3 10 0 5-3 6 3 6 3v9c-3 2-6-2-10 0-3 1.5-6 0-6 0z" />
  </svg>
)
export const IconAlert = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}>
    <path d="M12 3L2 21h20L12 3z" /><path d="M12 10v4M12 17.5v.01" />
  </svg>
)
export const IconLogout = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}>
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <path d="M16 17l5-5-5-5M21 12H9" />
  </svg>
)
export const IconCompany = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}>
    <path d="M3 21h18" /><path d="M5 21V5a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v16" />
    <path d="M19 21V9a1 1 0 0 0-1-1h-3" /><path d="M9 7h2M9 11h2M9 15h2" />
  </svg>
)
export const IconUser = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}>
    <circle cx="12" cy="8" r="4" /><path d="M4 21c0-4 4-6 8-6s8 2 8 6" />
  </svg>
)
export const IconChat = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}>
    <path d="M21 12a8 8 0 0 1-8 8H4l2-3a8 8 0 1 1 15-5z" />
  </svg>
)
export const IconArrowRight = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}><path d="M5 12h14M13 6l6 6-6 6" /></svg>
)
export const IconFilter = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}><path d="M4 6h16M7 12h10M10 18h4" /></svg>
)
export const IconMinus = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}><path d="M5 12h14" /></svg>
)
export const IconChevron = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}><path d="M6 9l6 6 6-6" /></svg>
)
export const IconSearch = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}>
    <circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" />
  </svg>
)
export const IconGoogle = (p: IconProps) => (
  <svg width={p.size || 18} height={p.size || 18} viewBox="0 0 24 24" fill="none" className={p.className} style={p.style} aria-hidden>
    <path d="M21.35 12.2c0-.7-.06-1.4-.18-2H12v3.8h5.3c-.2 1.2-.9 2.3-1.9 3v2.5h3c1.8-1.7 2.95-4.2 2.95-7.3z" fill="#4285F4" />
    <path d="M12 22c2.55 0 4.7-.85 6.3-2.3l-3-2.5c-.85.55-1.9.9-3.3.9-2.5 0-4.65-1.7-5.4-4H3.56v2.55C5.15 20.2 8.35 22 12 22z" fill="#34A853" />
    <path d="M6.6 14.1c-.2-.55-.3-1.15-.3-1.75s.1-1.2.3-1.75V8.05H3.56C3.2 8.7 3 9.55 3 10.35s.2 1.65.56 2.3L6.6 14.1z" fill="#FBBC05" />
    <path d="M12 5.9c1.4 0 2.65.48 3.65 1.4l2.7-2.7C16.75 3.05 14.6 2 12 2 8.35 2 5.15 3.8 3.56 8.05l3.04 2.3c.75-2.3 2.9-4.45 5.4-4.45z" fill="#EA4335" />
  </svg>
)
export const IconShield = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}>
    <path d="M12 2l8 3v6c0 5-3.5 8.5-8 11-4.5-2.5-8-6-8-11V5l8-3z" />
    <path d="M8.5 12l2.5 2.5L15.5 9.5" />
  </svg>
)
export const IconExternal = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}>
    <path d="M14 4h6v6" /><path d="M20 4l-9 9" /><path d="M19 13v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h6" />
  </svg>
)
export const IconRoadmap = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}>
    <circle cx="5" cy="6" r="2" /><circle cx="5" cy="18" r="2" />
    <path d="M7 6h14M7 18h10" /><circle cx="19" cy="6" r="1.4" fill="currentColor" stroke="none" />
  </svg>
)
export const IconTrophy = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}>
    <path d="M8 3h8v6a4 4 0 0 1-8 0V3z" />
    <path d="M8 5H4v2a3 3 0 0 0 3 3h2M16 5h4v2a3 3 0 0 1-3 3h-2M12 13v5M9 21h6M10 17h4" />
  </svg>
)
export const IconClock = (p: IconProps) => (
  <svg {...base(p.size, p.className, p.style)}>
    <circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" />
  </svg>
)
