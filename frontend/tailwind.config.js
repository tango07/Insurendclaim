/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { 50: "#eef6f5", 100: "#d5ebe8", 600: "#0f6e66", 700: "#0b5751", 900: "#06302d" },
      },
    },
  },
  plugins: [],
};
