import type { Config } from "tailwindcss";
const v = (n: string) => `var(--${n})`;

export default {
  content: ["./src/**/*.{ts,tsx}"],
  darkMode: ["selector", '[data-theme="floor"]'],
  theme: {
    extend: {
      colors: {
        bg: { base: v("bg-base"), raised: v("bg-raised"), sunken: v("bg-sunken") },
        ink: { DEFAULT: v("ink"), muted: v("ink-muted"), faint: v("ink-faint") },
        line: { DEFAULT: v("line"), strong: v("line-strong") },
        tag: { DEFAULT: v("tag"), ink: v("tag-ink"), wash: v("tag-wash") },
        uv: { DEFAULT: v("uv"), wash: v("uv-wash") },
        verified: { DEFAULT: v("verified"), wash: v("verified-wash") },
        seal: { DEFAULT: v("seal"), wash: v("seal-wash") },
        social: v("social"), market: v("market"), price: v("price"),
      },
      borderRadius: { cell: v("r-cell"), panel: v("r-panel"), chip: v("r-chip") },
      boxShadow: { pop: v("shadow-pop") },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        serif: ["var(--font-serif)", "Georgia", "serif"],
      },
      fontSize: {
        xs: ["12px", "16px"],
        sm: ["13px", "18px"],
        base: ["15px", "22px"],
        md: ["18px", "26px"],
        lg: ["22px", "30px"],
        xl: ["28px", "36px"],
        "2xl": ["36px", "42px"],
      },
      spacing: {
        rail: v("rail-w"),
        "rail-c": v("rail-w-collapsed"),
        topbar: v("topbar-h"),
        casebar: v("casebar-h"),
        row: v("row-h"),
      },
      maxWidth: { prose: "68ch" },
    },
  },
  plugins: [],
} satisfies Config;
