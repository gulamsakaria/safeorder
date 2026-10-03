import type { ReactNode } from 'react'

/** Small line icons (no image files needed). They take their colour from the text colour. */
function Svg({ children, size = 28 }: { children: ReactNode; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  )
}

export const Icons = {
  send: (
    <Svg>
      <path d="M22 2 11 13" />
      <path d="M22 2 15 22l-4-9-9-4 20-7z" />
    </Svg>
  ),
  pay: (
    <Svg>
      <rect x="2.5" y="5" width="19" height="14" rx="3" />
      <path d="M2.5 10h19" />
      <path d="M6.5 15h4" />
    </Svg>
  ),
  add: (
    <Svg>
      <rect x="3" y="3" width="18" height="18" rx="4" />
      <path d="M12 8v8M8 12h8" />
    </Svg>
  ),
  shop: (
    <Svg>
      <path d="M3 9.5 5 4h14l2 5.5" />
      <path d="M4 9.5V20h16V9.5" />
      <path d="M3 9.5c0 1.7 1.3 3 3 3s3-1.3 3-3c0 1.7 1.3 3 3 3s3-1.3 3-3c0 1.7 1.3 3 3 3s3-1.3 3-3" />
    </Svg>
  ),
  orders: (
    <Svg>
      <path d="M8 6h12M8 12h12M8 18h12" />
      <path d="M3.5 6h.01M3.5 12h.01M3.5 18h.01" />
    </Svg>
  ),
  history: (
    <Svg>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </Svg>
  ),
  shield: (
    <Svg>
      <path d="M12 3 4 6v6c0 4.5 3.2 8 8 9 4.8-1 8-4.5 8-9V6l-8-3z" />
      <path d="m9 12 2 2 4-4" />
    </Svg>
  ),
  home: (
    <Svg size={24}>
      <path d="M3 11 12 3l9 8" />
      <path d="M5 10v10h14V10" />
    </Svg>
  ),
  wallet: (
    <Svg size={24}>
      <path d="M3 7a2 2 0 0 1 2-2h13v4" />
      <path d="M3 7v11a2 2 0 0 0 2 2h15V9H5a2 2 0 0 1-2-2z" />
      <path d="M16 14.5h.01" />
    </Svg>
  ),
  clock: (
    <Svg size={24}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </Svg>
  ),
  more: (
    <Svg size={24}>
      <path d="M5 12h.01M12 12h.01M19 12h.01" />
    </Svg>
  ),
  scan: (
    <Svg size={30}>
      <path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3" />
      <path d="M8 12h8" />
    </Svg>
  ),
  user: (
    <Svg>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4 3.6-7 8-7s8 3 8 7" />
    </Svg>
  ),
  guide: (
    <Svg>
      <path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5z" />
      <path d="M9 8h6M9 12h6" />
    </Svg>
  ),
  admin: (
    <Svg>
      <path d="M12 3 4 6v6c0 4.5 3.2 8 8 9 4.8-1 8-4.5 8-9V6l-8-3z" />
      <circle cx="12" cy="11" r="2" />
      <path d="M8.5 16c.7-1.5 2-2.2 3.5-2.2s2.8.7 3.5 2.2" />
    </Svg>
  ),
  lock: (
    <Svg>
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" />
    </Svg>
  ),
  globe: (
    <Svg>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18" />
    </Svg>
  ),
  switch: (
    <Svg>
      <path d="M7 4 3 8l4 4M3 8h14M17 20l4-4-4-4M21 16H7" />
    </Svg>
  ),
  logout: (
    <Svg>
      <path d="M9 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h4" />
      <path d="m16 8 4 4-4 4M20 12H9" />
    </Svg>
  ),
  chart: (
    <Svg>
      <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
    </Svg>
  ),
}
