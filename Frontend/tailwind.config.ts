import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./client/index.html", "./client/src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      borderRadius: {
        lg:  "0.625rem",   /* 10px */
        md:  "0.5rem",     /* 8px  */
        sm:  "0.25rem",    /* 4px  */
        xl:  "0.875rem",   /* 14px */
        "2xl": "1.125rem", /* 18px */
        "3xl": "1.5rem",   /* 24px */
      },
      fontFamily: {
        sans:    ["Inter", "system-ui", "sans-serif"],
        display: ["Outfit", "system-ui", "sans-serif"],
        mono:    ["JetBrains Mono", "monospace"],
      },
      colors: {
        background: "hsl(var(--background) / <alpha-value>)",
        foreground: "hsl(var(--foreground) / <alpha-value>)",
        border:     "hsl(var(--border) / <alpha-value>)",
        input:      "hsl(var(--input) / <alpha-value>)",
        ring:       "hsl(var(--ring) / <alpha-value>)",
        card: {
          DEFAULT:    "hsl(var(--card) / <alpha-value>)",
          foreground: "hsl(var(--card-foreground) / <alpha-value>)",
        },
        popover: {
          DEFAULT:    "hsl(var(--popover) / <alpha-value>)",
          foreground: "hsl(var(--popover-foreground) / <alpha-value>)",
        },
        primary: {
          DEFAULT:    "hsl(var(--primary) / <alpha-value>)",
          foreground: "hsl(var(--primary-foreground) / <alpha-value>)",
        },
        secondary: {
          DEFAULT:    "hsl(var(--secondary) / <alpha-value>)",
          foreground: "hsl(var(--secondary-foreground) / <alpha-value>)",
        },
        muted: {
          DEFAULT:    "hsl(var(--muted) / <alpha-value>)",
          foreground: "hsl(var(--muted-foreground) / <alpha-value>)",
        },
        accent: {
          DEFAULT:    "hsl(var(--accent) / <alpha-value>)",
          foreground: "hsl(var(--accent-foreground) / <alpha-value>)",
        },
        destructive: {
          DEFAULT:    "hsl(var(--destructive) / <alpha-value>)",
          foreground: "hsl(var(--destructive-foreground) / <alpha-value>)",
        },
        success: {
          DEFAULT:    "hsl(var(--success) / <alpha-value>)",
          foreground: "hsl(var(--success-foreground) / <alpha-value>)",
        },
        chart: {
          "1": "hsl(var(--chart-1) / <alpha-value>)",
          "2": "hsl(var(--chart-2) / <alpha-value>)",
          "3": "hsl(var(--chart-3) / <alpha-value>)",
          "4": "hsl(var(--chart-4) / <alpha-value>)",
          "5": "hsl(var(--chart-5) / <alpha-value>)",
        },
        sidebar: {
          DEFAULT:    "hsl(var(--sidebar) / <alpha-value>)",
          foreground: "hsl(var(--sidebar-foreground) / <alpha-value>)",
          border:     "hsl(var(--sidebar-border) / <alpha-value>)",
          primary:    "hsl(var(--sidebar-primary) / <alpha-value>)",
          "primary-foreground": "hsl(var(--sidebar-primary-foreground) / <alpha-value>)",
          accent:     "hsl(var(--sidebar-accent) / <alpha-value>)",
          "accent-foreground":  "hsl(var(--sidebar-accent-foreground) / <alpha-value>)",
          ring:       "hsl(var(--sidebar-ring) / <alpha-value>)",
        },
      },
      spacing: {
        "18": "4.5rem",
        "22": "5.5rem",
        "72": "18rem",
        "80": "20rem",
        "88": "22rem",
        "96": "24rem",
      },
      maxWidth: {
        container: "1440px",
        prose:     "68ch",
        form:      "28rem",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to:   { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to:   { height: "0" },
        },
        shimmer: {
          from: { backgroundPosition: "-200% 0" },
          to:   { backgroundPosition:  "200% 0"  },
        },
        "fade-in-up": {
          from: { opacity: "0", transform: "translateY(10px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to:   { opacity: "1" },
        },
        "slide-in-left": {
          from: { opacity: "0", transform: "translateX(-16px)" },
          to:   { opacity: "1", transform: "translateX(0)" },
        },
        "pulse-ring": {
          "0%":   { boxShadow: "0 0 0 0 hsl(var(--primary) / 0.4)" },
          "70%":  { boxShadow: "0 0 0 8px hsl(var(--primary) / 0)" },
          "100%": { boxShadow: "0 0 0 0 hsl(var(--primary) / 0)" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up":   "accordion-up 0.2s ease-out",
        shimmer:          "shimmer 1.6s ease-in-out infinite",
        "fade-in-up":     "fade-in-up 0.35s cubic-bezier(0.16, 1, 0.3, 1) both",
        "fade-in":        "fade-in 0.3s ease both",
        "slide-in-left":  "slide-in-left 0.3s cubic-bezier(0.16, 1, 0.3, 1) both",
        "pulse-ring":     "pulse-ring 1.5s ease-out infinite",
      },
      transitionTimingFunction: {
        spring: "cubic-bezier(0.16, 1, 0.3, 1)",
      },
      boxShadow: {
        amber:    "0 1px 2px hsl(27 82% 35% / 0.06), 0 4px 12px hsl(27 82% 35% / 0.08), 0 0 0 1px hsl(var(--border) / 0.5)",
        "amber-lg": "0 2px 4px hsl(27 82% 35% / 0.08), 0 8px 24px hsl(27 82% 35% / 0.12), 0 0 0 1px hsl(var(--border) / 0.5)",
        "inner-top": "inset 0 1px 0 0 hsl(0 0% 100% / 0.06)",
      },
    },
  },
  plugins: [require("tailwindcss-animate"), require("@tailwindcss/typography")],
} satisfies Config;
