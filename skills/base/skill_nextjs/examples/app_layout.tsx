// Next.js 13+ App Router — Root layout with sidebar, top bar, and responsive mobile drawer
// File: app/layout.tsx (or app/(dashboard)/layout.tsx for nested layouts)
// Stack: Next.js + TypeScript + shadcn/ui + Tailwind CSS + next-themes
import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { ThemeProvider } from '@/components/theme-provider'
import { SidebarLayout } from '@/components/layout/sidebar-layout'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-sans',
  display: 'swap',
})

export const metadata: Metadata = {
  title: { default: 'Dashboard', template: '%s | Dashboard' },
  description: 'Your application dashboard',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={inter.variable}>
      <body className="font-sans antialiased bg-background text-foreground">
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
          <SidebarLayout>{children}</SidebarLayout>
        </ThemeProvider>
      </body>
    </html>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// File: components/layout/sidebar-layout.tsx
// ─────────────────────────────────────────────────────────────────────────────
'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useTheme } from 'next-themes'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  LayoutDashboard, BarChart3, Users, Settings, Bell,
  Menu, Sun, Moon, LogOut, ChevronsUpDown,
} from 'lucide-react'

interface NavItem {
  label: string
  href: string
  icon: React.ComponentType<{ className?: string }>
  badge?: string
}

const NAV: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { label: 'Analytics', href: '/analytics', icon: BarChart3 },
  { label: 'Users', href: '/users', icon: Users, badge: '6' },
  { label: 'Settings', href: '/settings', icon: Settings },
]

const CURRENT_USER = { name: 'Sarah Johnson', email: 's.johnson@acmecorp.com', initials: 'SJ' }

function NavItemLink({ item, collapsed }: { item: NavItem; collapsed?: boolean }) {
  const pathname = usePathname()
  const isActive = pathname === item.href || pathname.startsWith(item.href + '/')
  const Icon = item.icon

  return (
    <Link
      href={item.href}
      className={cn(
        'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-150',
        collapsed ? 'justify-center px-2' : '',
        isActive
          ? 'bg-primary text-primary-foreground shadow-sm'
          : 'text-muted-foreground hover:text-foreground hover:bg-muted'
      )}
    >
      <Icon className="w-4 h-4 flex-shrink-0" />
      {!collapsed && (
        <>
          <span className="flex-1 truncate">{item.label}</span>
          {item.badge && (
            <span className={cn(
              'text-xs px-1.5 py-0.5 rounded-full font-semibold min-w-[1.25rem] text-center',
              isActive
                ? 'bg-primary-foreground/20 text-primary-foreground'
                : 'bg-muted text-muted-foreground'
            )}>
              {item.badge}
            </span>
          )}
        </>
      )}
    </Link>
  )
}

function Sidebar({ onClose }: { onClose?: () => void }) {
  const { theme, setTheme } = useTheme()

  return (
    <aside className="flex flex-col h-full w-60 bg-background border-r border-border">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 h-16 border-b border-border flex-shrink-0">
        <div className="w-7 h-7 rounded-lg bg-primary flex items-center justify-center flex-shrink-0">
          <LayoutDashboard className="w-4 h-4 text-primary-foreground" />
        </div>
        <span className="font-semibold text-sm text-foreground truncate">My Application</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-0.5">
        <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider px-3 mb-2">
          Main
        </p>
        {NAV.map(item => (
          <NavItemLink key={item.href} item={item} />
        ))}
      </nav>

      {/* Bottom: theme toggle + user */}
      <div className="border-t border-border p-3 space-y-1">
        {/* Theme toggle */}
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start gap-3 text-muted-foreground hover:text-foreground"
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        >
          {theme === 'dark'
            ? <Sun className="w-4 h-4" />
            : <Moon className="w-4 h-4" />
          }
          <span className="text-sm">{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>
        </Button>

        {/* User menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center gap-3 w-full px-2 py-2 rounded-lg hover:bg-muted transition-colors text-left group">
              <Avatar className="h-8 w-8 flex-shrink-0">
                <AvatarFallback className="text-xs font-bold bg-primary/10 text-primary">
                  {CURRENT_USER.initials}
                </AvatarFallback>
              </Avatar>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">{CURRENT_USER.name}</p>
                <p className="text-xs text-muted-foreground truncate">{CURRENT_USER.email}</p>
              </div>
              <ChevronsUpDown className="w-4 h-4 text-muted-foreground flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent side="top" align="start" className="w-56">
            <div className="px-2 py-1.5">
              <p className="text-sm font-medium">{CURRENT_USER.name}</p>
              <p className="text-xs text-muted-foreground">{CURRENT_USER.email}</p>
            </div>
            <DropdownMenuSeparator />
            <DropdownMenuItem>Profile settings</DropdownMenuItem>
            <DropdownMenuItem>Billing & usage</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="text-red-600 focus:text-red-600 focus:bg-red-50 dark:focus:bg-red-950/20">
              <LogOut className="w-4 h-4 mr-2" />Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </aside>
  )
}

function TopBar({ title }: { title?: string }) {
  const pathname = usePathname()
  const pageTitle = title || NAV.find(n => pathname.startsWith(n.href))?.label || 'Dashboard'

  return (
    <header className="h-14 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 flex items-center px-4 gap-3 flex-shrink-0 sticky top-0 z-40">
      {/* Mobile menu trigger */}
      <Sheet>
        <SheetTrigger asChild>
          <Button variant="ghost" size="icon" className="lg:hidden -ml-1">
            <Menu className="w-5 h-5" />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="p-0 w-60">
          <Sidebar />
        </SheetContent>
      </Sheet>

      {/* Breadcrumb / page title */}
      <div className="flex items-center gap-2 flex-1 min-w-0">
        <h1 className="text-sm font-semibold text-foreground truncate">{pageTitle}</h1>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="icon" className="relative h-9 w-9">
          <Bell className="w-4.5 h-4.5 text-muted-foreground" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-primary rounded-full ring-2 ring-background" />
        </Button>
        <Avatar className="h-8 w-8 cursor-pointer">
          <AvatarFallback className="text-xs font-bold bg-primary/10 text-primary">
            {CURRENT_USER.initials}
          </AvatarFallback>
        </Avatar>
      </div>
    </header>
  )
}

export function SidebarLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Desktop sidebar — hidden on mobile */}
      <div className="hidden lg:flex flex-shrink-0">
        <Sidebar />
      </div>

      {/* Main content area */}
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// File: app/dashboard/page.tsx
// ─────────────────────────────────────────────────────────────────────────────
import type { Metadata } from 'next'

export const metadata: Metadata = { title: 'Dashboard' }

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-foreground">Good morning</h2>
        <p className="text-muted-foreground mt-1">Here's what's happening with your team today.</p>
      </div>
      {/* Import KPIGrid and UsersDataTable from dashboard_components.tsx */}
    </div>
  )
}
