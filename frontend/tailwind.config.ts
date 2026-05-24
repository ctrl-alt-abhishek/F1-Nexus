import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        primary: "#b91a24",
        "on-surface": "#ffffff",
        "on-surface-variant": "#9ca3af",
        "surface-container-low": "#0b1c30",
        "surface-container-high": "#111111",
        "glass-hover": "rgba(185, 26, 36, 0.1)",
      },
      spacing: {
        "margin-desktop": "40px",
        "panel-gap": "24px",
      },
    },
  },
  plugins: [],
};
export default config;
