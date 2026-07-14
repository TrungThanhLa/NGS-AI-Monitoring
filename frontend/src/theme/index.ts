import type { ThemeConfig } from 'antd'

// ── NGS Brand Colors (from official logo) ──────────────────────────────────────
export const BRAND = {
  navy:  '#0B2262',   // N block — dark navy blue (primary)
  gray:  '#8C95A0',   // G block — medium gray
  teal:  '#00859A',   // S block — teal (accent)
  tealDark:  '#006778', // darker teal for hover
  tealLight: '#E6F4F7', // teal light bg
  navyLight: '#E8EBF4',
  siderBg:   '#0A1D55', // sidebar background — slightly deeper than navy
  siderSub:  '#0D2468', // sub-menu bg
}

export const theme: ThemeConfig = {
  token: {
    colorPrimary:    BRAND.teal,
    colorSuccess:    '#52C41A',
    colorWarning:    '#FAAD14',
    colorError:      '#F5222D',
    colorInfo:       BRAND.teal,
    borderRadius:    8,
    fontFamily:      "'Inter', 'Segoe UI', Arial, sans-serif",
    colorBgLayout:   '#F5F7FA',
    colorBgContainer:'#FFFFFF',
    colorBorder:     '#E5E7EB',
    colorLink:       BRAND.teal,
    colorLinkHover:  BRAND.tealDark,
  },
  components: {
    Layout: {
      siderBg:  BRAND.siderBg,
      headerBg: '#FFFFFF',
    },
    Menu: {
      darkItemBg:          BRAND.siderBg,
      darkSubMenuItemBg:   BRAND.siderSub,
      darkItemSelectedBg:  BRAND.teal,
      darkItemHoverBg:     'rgba(0,133,154,0.18)',
      darkItemColor:       'rgba(255,255,255,0.72)',
      darkItemSelectedColor:'#FFFFFF',
    },
    Button: {
      controlHeight:      40,
      colorPrimary:       BRAND.teal,
      colorPrimaryHover:  BRAND.tealDark,
      colorPrimaryActive: BRAND.tealDark,
    },
    Table: {
      headerBg: '#F5F7FA',
    },
    Card: {
      boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
    },
    Tabs: {
      inkBarColor:        BRAND.teal,
      itemSelectedColor:  BRAND.teal,
      itemHoverColor:     BRAND.teal,
    },
    Switch: {
      colorPrimary:      BRAND.teal,
      colorPrimaryHover: BRAND.tealDark,
    },
    Checkbox: {
      colorPrimary:      BRAND.teal,
      colorPrimaryHover: BRAND.tealDark,
    },
    Badge: {
      colorPrimary: BRAND.teal,
    },
    Pagination: {
      colorPrimary:      BRAND.teal,
      colorPrimaryHover: BRAND.tealDark,
    },
  },
}

export const COLORS = {
  primary:      BRAND.navy,
  accent:       BRAND.teal,
  gray:         BRAND.gray,
  success:      '#52C41A',
  warning:      '#FAAD14',
  error:        '#F5222D',
  info:         BRAND.teal,
  background:   '#F5F7FA',
  card:         '#FFFFFF',
  border:       '#E5E7EB',
  chartPalette: [BRAND.teal, BRAND.navy, '#52C41A', '#FAAD14', '#F5222D', BRAND.gray],
}
