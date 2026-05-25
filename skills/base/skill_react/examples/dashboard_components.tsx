// Production-quality dashboard UI components — KPI grid, data table, sidebar nav
// Stack: React + TypeScript + shadcn/ui + Tailwind CSS + lucide-react
import React, { useState } from 'react'
import { cn } from '@/lib/utils'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  TrendingUp, TrendingDown, Users, DollarSign, Activity, BarChart3,
  MoreHorizontal, ChevronLeft, ChevronRight, Bell, Search, Menu,
  Home, Settings, LogOut, ChevronRight as Chevron,
} from 'lucide-react'

// ─── Types ────────────────────────────────────────────────────────────────────

interface KPIMetric {
  label: string
  value: string
  change: string
  trend: 'up' | 'down' | 'neutral'
  period: string
  icon: React.ComponentType<{ className?: string }>
}

interface TableUser {
  id: number
  name: string
  email: string
  role: string
  status: 'Active' | 'Inactive' | 'Pending'
  lastSeen: string
}

// ─── Sample data ─────────────────────────────────────────────────────────────

const METRICS: KPIMetric[] = [
  { label: 'Total Revenue', value: '$124,580', change: '+12.4%', trend: 'up', period: 'vs last month', icon: DollarSign },
  { label: 'Active Users', value: '8,249', change: '+3.2%', trend: 'up', period: 'vs last month', icon: Users },
  { label: 'Conversion Rate', value: '3.6%', change: '-0.8%', trend: 'down', period: 'vs last month', icon: Activity },
  { label: 'Avg Session', value: '4m 32s', change: '+18s', trend: 'up', period: 'vs last month', icon: BarChart3 },
]

const USERS: TableUser[] = [
  { id: 1, name: 'Sarah Johnson', email: 's.johnson@acmecorp.com', role: 'Admin', status: 'Active', lastSeen: 'just now' },
  { id: 2, name: 'Michael Williams', email: 'm.williams@acmecorp.com', role: 'Editor', status: 'Active', lastSeen: '2 min ago' },
  { id: 3, name: 'Emma Chen', email: 'e.chen@startup.io', role: 'Viewer', status: 'Inactive', lastSeen: 'yesterday' },
  { id: 4, name: 'James Garcia', email: 'j.garcia@enterprise.net', role: 'Manager', status: 'Active', lastSeen: '1 hour ago' },
  { id: 5, name: 'Olivia Davis', email: 'o.davis@acmecorp.com', role: 'Analyst', status: 'Pending', lastSeen: '3 days ago' },
  { id: 6, name: 'Noah Martinez', email: 'n.martinez@techventures.io', role: 'Developer', status: 'Active', lastSeen: '5 min ago' },
]

// ─── KPI Card ────────────────────────────────────────────────────────────────

function KPICard({ metric }: { metric: KPIMetric }) {
  const Icon = metric.icon
  const isUp = metric.trend === 'up'
  const isDown = metric.trend === 'down'

  return (
    <Card className="relative overflow-hidden transition-shadow hover:shadow-md">
      {/* Colored top accent */}
      <div className={cn(
        'absolute top-0 left-0 right-0 h-0.5',
        isUp ? 'bg-emerald-500' : isDown ? 'bg-red-500' : 'bg-blue-500'
      )} />
      <CardContent className="pt-6 pb-5">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium text-muted-foreground">{metric.label}</p>
            <p className="text-3xl font-bold tracking-tight text-foreground">{metric.value}</p>
          </div>
          <div className={cn(
            'p-2.5 rounded-xl',
            isUp ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-900/20 dark:text-emerald-400'
              : isDown ? 'bg-red-50 text-red-600 dark:bg-red-900/20 dark:text-red-400'
              : 'bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400'
          )}>
            <Icon className="w-5 h-5" />
          </div>
        </div>
        <div className="flex items-center gap-1.5 mt-4">
          {isUp
            ? <TrendingUp className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0" />
            : <TrendingDown className="w-3.5 h-3.5 text-red-500 flex-shrink-0" />
          }
          <span className={cn(
            'text-sm font-semibold',
            isUp ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'
          )}>
            {metric.change}
          </span>
          <span className="text-sm text-muted-foreground">{metric.period}</span>
        </div>
      </CardContent>
    </Card>
  )
}

// ─── KPI Grid ────────────────────────────────────────────────────────────────

export function KPIGrid({ metrics = METRICS }: { metrics?: KPIMetric[] }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
      {metrics.map((m, i) => <KPICard key={i} metric={m} />)}
    </div>
  )
}

// ─── Status Badge ────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: TableUser['status'] }) {
  const config = {
    Active:   { dot: 'bg-emerald-500', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-400 dark:border-emerald-800' },
    Inactive: { dot: 'bg-gray-400',    cls: 'bg-gray-100 text-gray-600 border-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:border-gray-700' },
    Pending:  { dot: 'bg-amber-500',   cls: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-900/20 dark:text-amber-400 dark:border-amber-800' },
  }[status]

  return (
    <span className={cn(
      'inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border',
      config.cls
    )}>
      <span className={cn('w-1.5 h-1.5 rounded-full', config.dot)} />
      {status}
    </span>
  )
}

// ─── Data Table ──────────────────────────────────────────────────────────────

export function UsersDataTable({ users = USERS }: { users?: TableUser[] }) {
  const [page, setPage] = useState(1)
  const PER_PAGE = 5
  const totalPages = Math.ceil(users.length / PER_PAGE)
  const paginated = users.slice((page - 1) * PER_PAGE, page * PER_PAGE)

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-4">
        <div>
          <CardTitle className="text-base font-semibold">Team Members</CardTitle>
          <p className="text-sm text-muted-foreground mt-0.5">{users.length} total members</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm">Export</Button>
          <Button size="sm">+ Add Member</Button>
        </div>
      </CardHeader>

      <div className="overflow-x-auto border-t">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-muted/40">
              <th className="text-left py-3 px-4 font-medium text-muted-foreground text-xs uppercase tracking-wider">User</th>
              <th className="text-left py-3 px-4 font-medium text-muted-foreground text-xs uppercase tracking-wider">Role</th>
              <th className="text-left py-3 px-4 font-medium text-muted-foreground text-xs uppercase tracking-wider">Status</th>
              <th className="text-left py-3 px-4 font-medium text-muted-foreground text-xs uppercase tracking-wider hidden sm:table-cell">Last Seen</th>
              <th className="py-3 px-4 w-10" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {paginated.map(user => (
              <tr key={user.id} className="hover:bg-muted/30 transition-colors">
                <td className="py-3.5 px-4">
                  <div className="flex items-center gap-3">
                    <Avatar className="h-8 w-8 flex-shrink-0">
                      <AvatarFallback className="text-xs font-semibold bg-primary/10 text-primary">
                        {user.name.split(' ').map(n => n[0]).join('')}
                      </AvatarFallback>
                    </Avatar>
                    <div className="min-w-0">
                      <div className="font-medium text-foreground truncate">{user.name}</div>
                      <div className="text-xs text-muted-foreground truncate">{user.email}</div>
                    </div>
                  </div>
                </td>
                <td className="py-3.5 px-4 text-muted-foreground">{user.role}</td>
                <td className="py-3.5 px-4"><StatusBadge status={user.status} /></td>
                <td className="py-3.5 px-4 text-muted-foreground hidden sm:table-cell">{user.lastSeen}</td>
                <td className="py-3.5 px-4">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="w-8 h-8 text-muted-foreground hover:text-foreground">
                        <MoreHorizontal className="w-4 h-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-36">
                      <DropdownMenuItem>View profile</DropdownMenuItem>
                      <DropdownMenuItem>Edit role</DropdownMenuItem>
                      <DropdownMenuItem className="text-red-600">Remove</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t">
          <p className="text-sm text-muted-foreground">
            Showing {(page - 1) * PER_PAGE + 1}–{Math.min(page * PER_PAGE, users.length)} of {users.length}
          </p>
          <div className="flex items-center gap-1">
            <Button variant="outline" size="icon" className="h-8 w-8"
              onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
              <ChevronLeft className="w-4 h-4" />
            </Button>
            {Array.from({ length: totalPages }, (_, i) => i + 1).map(p => (
              <Button key={p} variant={p === page ? 'default' : 'outline'}
                size="icon" className="h-8 w-8 text-sm"
                onClick={() => setPage(p)}>
                {p}
              </Button>
            ))}
            <Button variant="outline" size="icon" className="h-8 w-8"
              onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}>
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}

// ─── Sidebar Navigation ──────────────────────────────────────────────────────

interface NavItem {
  label: string
  icon: React.ComponentType<{ className?: string }>
  href: string
  badge?: string
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', icon: Home, href: '/' },
  { label: 'Analytics', icon: BarChart3, href: '/analytics' },
  { label: 'Users', icon: Users, href: '/users', badge: '6' },
  { label: 'Settings', icon: Settings, href: '/settings' },
]

export function SidebarNav({
  currentPath = '/',
  userName = 'Sarah Johnson',
  userEmail = 's.johnson@acmecorp.com',
}: {
  currentPath?: string
  userName?: string
  userEmail?: string
}) {
  return (
    <nav className="flex flex-col h-full bg-background border-r border-border w-60 flex-shrink-0">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 h-16 border-b border-border flex-shrink-0">
        <div className="w-7 h-7 rounded-lg bg-primary flex items-center justify-center">
          <BarChart3 className="w-4 h-4 text-primary-foreground" />
        </div>
        <span className="font-semibold text-foreground text-sm">Dashboard App</span>
      </div>

      {/* Nav items */}
      <div className="flex-1 overflow-y-auto py-4 px-3 space-y-0.5">
        {NAV_ITEMS.map(item => {
          const Icon = item.icon
          const isActive = currentPath === item.href
          return (
            <a
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted'
              )}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span className="flex-1">{item.label}</span>
              {item.badge && (
                <span className={cn(
                  'text-xs px-1.5 py-0.5 rounded-full font-semibold',
                  isActive ? 'bg-primary-foreground/20 text-primary-foreground' : 'bg-muted text-muted-foreground'
                )}>
                  {item.badge}
                </span>
              )}
            </a>
          )
        })}
      </div>

      {/* User profile */}
      <div className="border-t border-border p-3">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center gap-3 w-full px-2 py-2 rounded-lg hover:bg-muted transition-colors text-left">
              <Avatar className="h-8 w-8 flex-shrink-0">
                <AvatarFallback className="text-xs font-semibold bg-primary/10 text-primary">
                  {userName.split(' ').map(n => n[0]).join('')}
                </AvatarFallback>
              </Avatar>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">{userName}</p>
                <p className="text-xs text-muted-foreground truncate">{userEmail}</p>
              </div>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent side="top" align="start" className="w-52">
            <DropdownMenuItem>Profile settings</DropdownMenuItem>
            <DropdownMenuItem>Billing</DropdownMenuItem>
            <DropdownMenuItem className="text-red-600">
              <LogOut className="w-4 h-4 mr-2" />Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </nav>
  )
}

// ─── Top Bar ──────────────────────────────────────────────────────────────────

export function TopBar({ title = 'Dashboard', onMenuClick }: { title?: string; onMenuClick?: () => void }) {
  return (
    <header className="h-16 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 flex items-center px-4 gap-3 flex-shrink-0">
      <Button variant="ghost" size="icon" className="lg:hidden" onClick={onMenuClick}>
        <Menu className="w-5 h-5" />
      </Button>
      <div className="flex-1">
        <h1 className="font-semibold text-foreground text-sm">{title}</h1>
      </div>
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="icon" className="relative">
          <Bell className="w-5 h-5 text-muted-foreground" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full" />
        </Button>
      </div>
    </header>
  )
}

// ─── Full Dashboard Layout Example ───────────────────────────────────────────

export default function DashboardPage() {
  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <SidebarNav currentPath="/" />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar title="Overview" />
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">
            <div>
              <h2 className="text-2xl font-bold tracking-tight">Good morning, Sarah</h2>
              <p className="text-muted-foreground mt-1">Here's what's happening with your team today.</p>
            </div>
            <KPIGrid />
            <UsersDataTable />
          </div>
        </main>
      </div>
    </div>
  )
}
