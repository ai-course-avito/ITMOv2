/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#7c3aed',
          fg: '#ffffff',
        },
        accent: '#22d3ee'
      },
    },
  },
  plugins: [],
}
