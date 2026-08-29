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
