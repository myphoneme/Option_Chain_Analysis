import type { Config } from "tailwindcss";

/**
 * Design tokens mirrored from the QuantTrade portal
 * (myphoneme/quant-trade → client/src/index.css) so this app renders as a
 * native portal page rather than a separately-styled site.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#fff7ed",
          100: "#ffedd5",
          200: "#fed7aa",
          300: "#fdba74",
          400: "#fb923c",
          500: "#F47920",   // QuantTrade primary
          600: "#EA580C",
          700: "#c2410c",
          800: "#9a3412",
          900: "#7c2d12",
        },
        // Kept for the analyzer's own bull/bear semantics.
        bull: "#16a34a",
        bear: "#dc2626",
        flat: "#64748b",
        accent: "#F47920",
      },
    },
  },
  plugins: [],
};
export default config;
