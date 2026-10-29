/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        'quant-canvas': '#0b0f19',
        'quant-workbench': '#111827',
        'quant-card': '#182234',
        'quant-card-hover': '#1e293b',
        'quant-border': '#334155',
        'quant-red': '#e74c3c',
        'quant-neon-red': '#ff4757',
        'quant-blue': '#3498db',
        'quant-neon-blue': '#00d2d3',
      },
      boxShadow: {
        'neon-red': '0 0 12px rgba(255, 71, 87, 0.85)',
        'neon-blue': '0 0 12px rgba(0, 210, 211, 0.9)',
      },
    },
  },
  plugins: [],
};
