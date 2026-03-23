import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        sand: "#f6efe6",
        paper: "#fffdf9",
        ink: "#251814",
        cocoa: "#5f3b2f",
        clay: "#bc6c4e",
        blush: "#f1d7ce",
        mist: "#efe7df",
        line: "#e4d4c5",
        pine: "#1f5d4d",
        sky: "#cfe1f7",
        honey: "#f5e2a7",
        rose: "#f6d3d9"
      },
      boxShadow: {
        panel: "0 18px 50px rgba(62, 37, 28, 0.08)"
      },
      borderRadius: {
        panel: "28px",
        card: "24px"
      },
      fontFamily: {
        sans: ["'Space Grotesk'", "'Avenir Next'", "system-ui", "sans-serif"],
        mono: ["'IBM Plex Mono'", "'SFMono-Regular'", "monospace"]
      }
    }
  },
  plugins: []
};

export default config;
