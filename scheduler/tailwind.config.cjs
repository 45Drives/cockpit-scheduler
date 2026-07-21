/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
			fontFamily: {},
			colors: {
				neutral: {
					850: "#222222",
				}
			},
			keyframes: {
				'indeterminate-slide': {
					'0%':   { transform: 'translateX(-100%)' },
					'100%': { transform: 'translateX(400%)' },
				},
			},
			animation: {
				'indeterminate': 'indeterminate-slide 1.5s ease-in-out infinite',
			},
		},
  },
  plugins: [
    require('@tailwindcss/forms')
  ],
  darkMode: 'class',
}
