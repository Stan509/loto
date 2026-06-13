/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./admin_portal/templates/**/*.html",
    "./agent_portal/templates/**/*.html",
    "./tickets/templates/**/*.html",
    "./templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        gaboom: {
          orange: "#FF7A00",
          navy: "#0B1C3D",
        },
        "deep-night": "#020617",
        "slate-dark": "#0F172A",
      },
      fontFamily: {
        jakarta: ["'Plus Jakarta Sans'", "sans-serif"],
        inter: ["Inter", "sans-serif"],
      },
      boxShadow: {
        glowOrange: "0 0 0 1px rgba(255,122,0,0.15), 0 10px 30px rgba(255,122,0,0.25)",
        glowBlue: "0 0 0 1px rgba(62,138,255,0.18), 0 10px 30px rgba(62,138,255,0.20)",
        "glow-orange": "0 0 25px -5px rgba(255, 122, 0, 0.4)",
        "glow-blue": "0 0 25px -5px rgba(59, 130, 246, 0.4)",
      },
      keyframes: {
        gradientShift: {
          "0%,100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
      },
      animation: {
        gradientShift: "gradientShift 12s ease infinite",
      },
    },
  },
  plugins: [],
};
