<!--
  Production-quality Vue 3 dashboard — KPI cards, data table, sidebar nav
  Stack: Vue 3 Composition API + TypeScript + Tailwind CSS + @headlessui/vue
-->
<script setup lang="ts">
import { ref, computed } from 'vue'

// ─── Types ────────────────────────────────────────────────────────────────────

interface KPIMetric {
  label: string
  value: string
  change: string
  trend: 'up' | 'down' | 'neutral'
  period: string
  icon: string  // emoji or icon name
}

interface TableUser {
  id: number
  name: string
  email: string
  role: string
  status: 'Active' | 'Inactive' | 'Pending'
  lastSeen: string
}

interface NavItem {
  label: string
  icon: string
  href: string
  badge?: string
}

// ─── Mock data ────────────────────────────────────────────────────────────────

const metrics: KPIMetric[] = [
  { label: 'Total Revenue',   value: '$124,580', change: '+12.4%', trend: 'up',   period: 'vs last month', icon: '💰' },
  { label: 'Active Users',    value: '8,249',    change: '+3.2%',  trend: 'up',   period: 'vs last month', icon: '👥' },
  { label: 'Conversion Rate', value: '3.6%',     change: '-0.8%',  trend: 'down', period: 'vs last month', icon: '📈' },
  { label: 'Avg Session',     value: '4m 32s',   change: '+18s',   trend: 'up',   period: 'vs last month', icon: '⏱️' },
]

const users: TableUser[] = [
  { id: 1, name: 'Sarah Johnson',    email: 's.johnson@acmecorp.com',  role: 'Admin',     status: 'Active',   lastSeen: 'just now' },
  { id: 2, name: 'Michael Williams', email: 'm.williams@acmecorp.com', role: 'Editor',    status: 'Active',   lastSeen: '2 min ago' },
  { id: 3, name: 'Emma Chen',        email: 'e.chen@startup.io',       role: 'Viewer',    status: 'Inactive', lastSeen: 'yesterday' },
  { id: 4, name: 'James Garcia',     email: 'j.garcia@enterprise.net', role: 'Manager',   status: 'Active',   lastSeen: '1 hour ago' },
  { id: 5, name: 'Olivia Davis',     email: 'o.davis@acmecorp.com',    role: 'Analyst',   status: 'Pending',  lastSeen: '3 days ago' },
]

const navItems: NavItem[] = [
  { label: 'Dashboard', icon: '🏠', href: '/' },
  { label: 'Analytics', icon: '📊', href: '/analytics' },
  { label: 'Users',     icon: '👥', href: '/users', badge: '5' },
  { label: 'Settings',  icon: '⚙️', href: '/settings' },
]

// ─── State ────────────────────────────────────────────────────────────────────

const currentPath = ref('/')
const sidebarOpen = ref(false)
const page = ref(1)
const PER_PAGE = 5

const paginatedUsers = computed(() =>
  users.slice((page.value - 1) * PER_PAGE, page.value * PER_PAGE)
)
const totalPages = computed(() => Math.ceil(users.length / PER_PAGE))

// ─── Helpers ─────────────────────────────────────────────────────────────────

function initials(name: string) {
  return name.split(' ').map(n => n[0]).join('')
}

function statusClass(status: TableUser['status']) {
  return {
    Active:   'bg-emerald-50 text-emerald-700 border-emerald-200',
    Inactive: 'bg-gray-100 text-gray-600 border-gray-200',
    Pending:  'bg-amber-50 text-amber-700 border-amber-200',
  }[status]
}

function statusDot(status: TableUser['status']) {
  return {
    Active:   'bg-emerald-500',
    Inactive: 'bg-gray-400',
    Pending:  'bg-amber-500',
  }[status]
}

function trendClass(trend: KPIMetric['trend']) {
  return trend === 'up' ? 'text-emerald-600' : trend === 'down' ? 'text-red-600' : 'text-blue-600'
}

function trendBgClass(trend: KPIMetric['trend']) {
  return trend === 'up' ? 'bg-emerald-50' : trend === 'down' ? 'bg-red-50' : 'bg-blue-50'
}

function trendBorderClass(trend: KPIMetric['trend']) {
  return trend === 'up' ? 'bg-emerald-500' : trend === 'down' ? 'bg-red-500' : 'bg-blue-500'
}
</script>

<template>
  <div class="flex h-screen bg-white overflow-hidden font-sans">

    <!-- ── Sidebar ─────────────────────────────────────────────────────────── -->
    <aside class="hidden lg:flex flex-col w-60 border-r border-gray-200 bg-white flex-shrink-0">
      <!-- Logo -->
      <div class="flex items-center gap-2.5 px-5 h-16 border-b border-gray-200 flex-shrink-0">
        <div class="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center text-white text-sm font-bold">
          D
        </div>
        <span class="font-semibold text-sm text-gray-900">Dashboard App</span>
      </div>

      <!-- Nav items -->
      <nav class="flex-1 overflow-y-auto py-4 px-3 space-y-0.5">
        <a
          v-for="item in navItems"
          :key="item.href"
          :href="item.href"
          :class="[
            'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-150',
            currentPath === item.href
              ? 'bg-indigo-600 text-white'
              : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
          ]"
        >
          <span class="text-base leading-none">{{ item.icon }}</span>
          <span class="flex-1">{{ item.label }}</span>
          <span
            v-if="item.badge"
            :class="[
              'text-xs px-1.5 py-0.5 rounded-full font-semibold',
              currentPath === item.href
                ? 'bg-white/20 text-white'
                : 'bg-gray-100 text-gray-500'
            ]"
          >{{ item.badge }}</span>
        </a>
      </nav>

      <!-- User profile -->
      <div class="border-t border-gray-200 p-3">
        <div class="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-gray-100 cursor-pointer transition-colors">
          <div class="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 text-xs font-bold flex-shrink-0">
            SJ
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-gray-900 truncate">Sarah Johnson</p>
            <p class="text-xs text-gray-500 truncate">s.johnson@acmecorp.com</p>
          </div>
        </div>
      </div>
    </aside>

    <!-- ── Main area ────────────────────────────────────────────────────────── -->
    <div class="flex flex-col flex-1 overflow-hidden">

      <!-- Top bar -->
      <header class="h-14 border-b border-gray-200 bg-white flex items-center px-4 gap-3 flex-shrink-0">
        <button
          class="lg:hidden p-2 rounded-md text-gray-500 hover:text-gray-700 hover:bg-gray-100"
          @click="sidebarOpen = !sidebarOpen"
        >
          ☰
        </button>
        <div class="flex-1">
          <h1 class="text-sm font-semibold text-gray-900">Overview</h1>
        </div>
        <button class="relative p-2 rounded-md text-gray-500 hover:text-gray-700 hover:bg-gray-100">
          🔔
          <span class="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full" />
        </button>
      </header>

      <!-- Scrollable content -->
      <main class="flex-1 overflow-y-auto">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">

          <!-- Page heading -->
          <div>
            <h2 class="text-2xl font-bold tracking-tight text-gray-900">Good morning, Sarah</h2>
            <p class="text-gray-500 mt-1 text-sm">Here's what's happening with your team today.</p>
          </div>

          <!-- ── KPI Grid ──────────────────────────────────────────────────── -->
          <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <div
              v-for="metric in metrics"
              :key="metric.label"
              class="relative bg-white rounded-xl border border-gray-200 p-5 overflow-hidden transition-shadow hover:shadow-md"
            >
              <!-- Colored top accent -->
              <div :class="['absolute top-0 left-0 right-0 h-0.5', trendBorderClass(metric.trend)]" />

              <div class="flex items-start justify-between">
                <div class="space-y-1">
                  <p class="text-sm font-medium text-gray-500">{{ metric.label }}</p>
                  <p class="text-3xl font-bold text-gray-900 tracking-tight">{{ metric.value }}</p>
                </div>
                <div :class="['p-2.5 rounded-xl text-lg', trendBgClass(metric.trend)]">
                  {{ metric.icon }}
                </div>
              </div>

              <div class="flex items-center gap-1.5 mt-4">
                <span :class="['text-xs', trendClass(metric.trend)]">
                  {{ metric.trend === 'up' ? '▲' : '▼' }}
                </span>
                <span :class="['text-sm font-semibold', trendClass(metric.trend)]">
                  {{ metric.change }}
                </span>
                <span class="text-sm text-gray-400">{{ metric.period }}</span>
              </div>
            </div>
          </div>

          <!-- ── Users Table ─────────────────────────────────────────────── -->
          <div class="bg-white rounded-xl border border-gray-200 overflow-hidden">

            <!-- Table header -->
            <div class="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <div>
                <h3 class="text-sm font-semibold text-gray-900">Team Members</h3>
                <p class="text-xs text-gray-500 mt-0.5">{{ users.length }} total members</p>
              </div>
              <div class="flex items-center gap-2">
                <button class="px-3 py-1.5 text-sm border border-gray-300 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors">
                  Export
                </button>
                <button class="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium">
                  + Add Member
                </button>
              </div>
            </div>

            <!-- Table -->
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="bg-gray-50">
                    <th class="text-left py-3 px-5 text-xs font-semibold text-gray-500 uppercase tracking-wider">User</th>
                    <th class="text-left py-3 px-5 text-xs font-semibold text-gray-500 uppercase tracking-wider">Role</th>
                    <th class="text-left py-3 px-5 text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                    <th class="text-left py-3 px-5 text-xs font-semibold text-gray-500 uppercase tracking-wider hidden sm:table-cell">Last Seen</th>
                    <th class="py-3 px-5 w-10" />
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-100">
                  <tr
                    v-for="user in paginatedUsers"
                    :key="user.id"
                    class="hover:bg-gray-50 transition-colors"
                  >
                    <!-- User cell -->
                    <td class="py-3.5 px-5">
                      <div class="flex items-center gap-3">
                        <div class="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 text-xs font-bold flex-shrink-0">
                          {{ initials(user.name) }}
                        </div>
                        <div class="min-w-0">
                          <div class="font-medium text-gray-900 truncate">{{ user.name }}</div>
                          <div class="text-xs text-gray-500 truncate">{{ user.email }}</div>
                        </div>
                      </div>
                    </td>

                    <td class="py-3.5 px-5 text-gray-600">{{ user.role }}</td>

                    <!-- Status badge -->
                    <td class="py-3.5 px-5">
                      <span :class="['inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border', statusClass(user.status)]">
                        <span :class="['w-1.5 h-1.5 rounded-full', statusDot(user.status)]" />
                        {{ user.status }}
                      </span>
                    </td>

                    <td class="py-3.5 px-5 text-gray-500 hidden sm:table-cell">{{ user.lastSeen }}</td>

                    <td class="py-3.5 px-5 text-right">
                      <button class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors">
                        ⋯
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- Pagination -->
            <div v-if="totalPages > 1" class="flex items-center justify-between px-5 py-3 border-t border-gray-100">
              <span class="text-sm text-gray-500">
                Showing {{ (page - 1) * PER_PAGE + 1 }}–{{ Math.min(page * PER_PAGE, users.length) }}
                of {{ users.length }}
              </span>
              <div class="flex items-center gap-1">
                <button
                  :disabled="page === 1"
                  class="w-8 h-8 flex items-center justify-center rounded-md border border-gray-200 text-gray-500 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-sm"
                  @click="page = Math.max(1, page - 1)"
                >‹</button>
                <button
                  v-for="p in totalPages"
                  :key="p"
                  :class="[
                    'w-8 h-8 flex items-center justify-center rounded-md text-sm font-medium transition-colors',
                    p === page
                      ? 'bg-indigo-600 text-white border border-indigo-600'
                      : 'border border-gray-200 text-gray-600 hover:bg-gray-50'
                  ]"
                  @click="page = p"
                >{{ p }}</button>
                <button
                  :disabled="page === totalPages"
                  class="w-8 h-8 flex items-center justify-center rounded-md border border-gray-200 text-gray-500 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-sm"
                  @click="page = Math.min(totalPages, page + 1)"
                >›</button>
              </div>
            </div>

          </div>
          <!-- end table card -->

        </div>
      </main>
    </div>

  </div>
</template>
