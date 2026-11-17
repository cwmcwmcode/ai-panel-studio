/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts}'],
  theme: {
    extend: {
      colors: {
        studio: {
          base: '#020617',
          panel: '#0f172a',
          line: '#1e293b'
        }
      },
      fontFamily: {
        sans: [
          'Inter',
          '"PingFang SC"',
          '"Microsoft YaHei"',
          '"Helvetica Neue"',
          'Arial',
          'sans-serif'
        ]
      },
      keyframes: {
        breathe: {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '50%': { opacity: '0.45', transform: 'scale(0.82)' }
        },
        glowIn: {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' }
        },
        scan: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(220%)' }
        }
      },
      animation: {
        breathe: 'breathe 1.6s ease-in-out infinite',
        'glow-in': 'glowIn 0.35s ease-out both',
        scan: 'scan 2.8s linear infinite'
      }
    }
  },
  plugins: []
}
