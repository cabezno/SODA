import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: {
    default: 'SODA Generated App',
    template: '%s | SODA'
  },
  description: 'Aplicación de alto rendimiento generada por SODA',
  openGraph: {
    type: 'website',
    locale: 'es_ES',
    url: 'https://soda.dev',
    siteName: 'SODA'
  },
  robots: {
    index: true,
    follow: true
  }
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  )
}
