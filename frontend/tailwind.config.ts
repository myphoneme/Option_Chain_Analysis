import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bull: "#16a34a",
        bear: "#dc2626",
        flat: "#64748b",
        accent: "#f97316", // matches the course's orange theme
      },
    },
  },
  plugins: [],
};
export default config;
