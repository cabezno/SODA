// Production-quality landing page — Hero + Features + Testimonials + CTA
// Stack: React + TypeScript + shadcn/ui + Tailwind CSS
import React from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { ArrowRight, Check, Star, Zap, Shield, Settings2, BarChart3 } from 'lucide-react'

// ─── Types ────────────────────────────────────────────────────────────────────

interface Feature {
  icon: React.ComponentType<{ className?: string }>
  title: string
  description: string
}

interface Testimonial {
  name: string
  role: string
  content: string
  avatar: string
  rating: number
}

interface PricingTier {
  name: string
  price: string
  period: string
  description: string
  features: string[]
  popular?: boolean
  cta: string
}

// ─── Content ──────────────────────────────────────────────────────────────────

const FEATURES: Feature[] = [
  {
    icon: Zap,
    title: 'Blazing Fast',
    description: 'Built on edge infrastructure with sub-100ms response times globally. Your users will never experience lag.',
  },
  {
    icon: Shield,
    title: 'Enterprise Security',
    description: 'SOC 2 Type II certified with end-to-end encryption, SSO/SAML, and granular role-based access control.',
  },
  {
    icon: Settings2,
    title: 'Fully Customizable',
    description: 'Every workflow, integration, and report tailored to exactly how your team works — no compromise.',
  },
  {
    icon: BarChart3,
    title: 'Real-time Analytics',
    description: 'Beautiful dashboards with live data. Know what\'s happening the moment it changes.',
  },
]

const TESTIMONIALS: Testimonial[] = [
  {
    name: 'Alexandra Chen',
    role: 'CTO at Veritas Health',
    content: 'We reduced our deployment cycle from 2 weeks to 4 hours. The ROI was immediate and undeniable.',
    avatar: 'AC',
    rating: 5,
  },
  {
    name: 'Marcus Williams',
    role: 'VP Engineering at Flux',
    content: 'Finally a tool that actually delivers on its promises. Our entire team adopted it in under a week.',
    avatar: 'MW',
    rating: 5,
  },
  {
    name: 'Priya Sharma',
    role: 'Lead Developer at Orbit',
    content: 'The developer experience is exceptional. I\'ve recommended it to every engineering team I know.',
    avatar: 'PS',
    rating: 5,
  },
]

const PRICING: PricingTier[] = [
  {
    name: 'Starter',
    price: '$0',
    period: 'forever',
    description: 'Perfect for individuals and small projects.',
    features: ['5 projects', '10 GB storage', 'Community support', 'Basic analytics'],
    cta: 'Get started free',
  },
  {
    name: 'Pro',
    price: '$29',
    period: '/month',
    description: 'Everything you need to scale your team.',
    features: ['Unlimited projects', '100 GB storage', 'Priority support', 'Advanced analytics', 'Custom domains', 'Team collaboration'],
    popular: true,
    cta: 'Start free trial',
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    period: '',
    description: 'For large organizations with custom needs.',
    features: ['Everything in Pro', 'SSO & SAML', 'Custom SLAs', 'Dedicated account manager', 'On-premise option'],
    cta: 'Contact sales',
  },
]

// ─── Navbar ───────────────────────────────────────────────────────────────────

export function LandingNavbar() {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="max-w-7xl mx-auto flex h-14 items-center px-4 sm:px-6">
        <a href="/" className="flex items-center gap-2 font-semibold mr-8">
          <div className="w-6 h-6 rounded bg-primary flex items-center justify-center">
            <Zap className="w-3.5 h-3.5 text-primary-foreground" />
          </div>
          <span>AppName</span>
        </a>
        <nav className="hidden md:flex items-center gap-1 flex-1">
          {['Features', 'Pricing', 'Docs', 'Blog'].map(item => (
            <a key={item} href={`#${item.toLowerCase()}`}
              className="text-sm text-muted-foreground hover:text-foreground px-3 py-1.5 rounded-md hover:bg-muted transition-colors">
              {item}
            </a>
          ))}
        </nav>
        <div className="flex items-center gap-2 ml-auto">
          <Button variant="ghost" size="sm">Log in</Button>
          <Button size="sm">Get started <ArrowRight className="w-3.5 h-3.5 ml-1.5" /></Button>
        </div>
      </div>
    </header>
  )
}

// ─── Hero Section ─────────────────────────────────────────────────────────────

export function HeroSection() {
  return (
    <section className="relative overflow-hidden">
      {/* Gradient background */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-secondary/5 pointer-events-none" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-primary/5 rounded-full blur-3xl pointer-events-none" />

      <div className="relative max-w-5xl mx-auto px-4 sm:px-6 pt-20 pb-24 text-center">
        {/* Announcement badge */}
        <div className="inline-flex items-center gap-2 mb-8">
          <Badge variant="outline" className="px-3 py-1 text-sm font-medium border-primary/30 text-primary bg-primary/5">
            <span className="mr-1.5">🎉</span>
            Version 2.0 is here
            <ArrowRight className="w-3 h-3 ml-1.5" />
          </Badge>
        </div>

        {/* Headline */}
        <h1 className="text-5xl sm:text-6xl md:text-7xl font-bold tracking-tight text-foreground leading-[1.1] mb-6">
          Build faster,{' '}
          <span className="bg-gradient-to-r from-primary to-primary/60 bg-clip-text text-transparent">
            ship smarter
          </span>
        </h1>

        {/* Subheadline */}
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto mb-10 leading-relaxed">
          The all-in-one platform that helps your team collaborate, automate, and deliver
          results — 10x faster than before. No setup required.
        </p>

        {/* CTAs */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mb-14">
          <Button size="lg" className="h-12 px-8 text-base font-medium">
            Start free trial
            <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
          <Button variant="outline" size="lg" className="h-12 px-8 text-base font-medium">
            Watch 2-min demo
          </Button>
        </div>

        {/* Social proof stats */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-8 text-sm text-muted-foreground">
          {[
            { value: '50K+', label: 'Teams worldwide' },
            { value: '99.9%', label: 'Uptime SLA' },
            { value: '4.9/5', label: 'Customer rating' },
          ].map(stat => (
            <div key={stat.label} className="flex items-center gap-2">
              <span className="font-bold text-foreground text-base">{stat.value}</span>
              <span>{stat.label}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── Features Grid ────────────────────────────────────────────────────────────

export function FeaturesSection() {
  return (
    <section id="features" className="py-20 bg-muted/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="text-center mb-14">
          <p className="text-sm font-semibold text-primary uppercase tracking-wider mb-3">Features</p>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-foreground">
            Everything you need to ship faster
          </h2>
          <p className="text-muted-foreground mt-3 max-w-xl mx-auto">
            A complete platform designed for modern teams who want to move fast without breaking things.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {FEATURES.map((feature, i) => {
            const Icon = feature.icon
            return (
              <Card key={i} className="border-border/60 hover:border-primary/30 hover:shadow-md transition-all duration-200 group">
                <CardContent className="pt-6">
                  <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center mb-4 group-hover:bg-primary/15 transition-colors">
                    <Icon className="w-5 h-5 text-primary" />
                  </div>
                  <h3 className="font-semibold text-foreground mb-2">{feature.title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">{feature.description}</p>
                </CardContent>
              </Card>
            )
          })}
        </div>
      </div>
    </section>
  )
}

// ─── Testimonials ─────────────────────────────────────────────────────────────

export function TestimonialsSection() {
  return (
    <section className="py-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="text-center mb-14">
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-foreground">
            Loved by engineering teams
          </h2>
          <p className="text-muted-foreground mt-3">Don't take our word for it.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {TESTIMONIALS.map((t, i) => (
            <Card key={i} className="border-border/60">
              <CardContent className="pt-6">
                <div className="flex gap-0.5 mb-4">
                  {Array.from({ length: t.rating }, (_, j) => (
                    <Star key={j} className="w-4 h-4 fill-amber-400 text-amber-400" />
                  ))}
                </div>
                <blockquote className="text-sm text-foreground leading-relaxed mb-5">
                  "{t.content}"
                </blockquote>
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full bg-primary/10 flex items-center justify-center text-primary text-xs font-bold flex-shrink-0">
                    {t.avatar}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">{t.name}</p>
                    <p className="text-xs text-muted-foreground">{t.role}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── Pricing ──────────────────────────────────────────────────────────────────

export function PricingSection() {
  return (
    <section id="pricing" className="py-20 bg-muted/30">
      <div className="max-w-5xl mx-auto px-4 sm:px-6">
        <div className="text-center mb-14">
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-foreground">Simple, transparent pricing</h2>
          <p className="text-muted-foreground mt-3">No hidden fees. Cancel anytime.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {PRICING.map((tier, i) => (
            <Card key={i} className={cn(
              'relative flex flex-col',
              tier.popular && 'border-primary shadow-lg shadow-primary/10'
            )}>
              {tier.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <Badge className="bg-primary text-primary-foreground px-3">Most popular</Badge>
                </div>
              )}
              <CardContent className="pt-8 pb-6 flex flex-col flex-1">
                <div className="mb-6">
                  <h3 className="font-semibold text-foreground">{tier.name}</h3>
                  <div className="flex items-baseline gap-1 mt-2">
                    <span className="text-4xl font-bold tracking-tight text-foreground">{tier.price}</span>
                    {tier.period && <span className="text-muted-foreground text-sm">{tier.period}</span>}
                  </div>
                  <p className="text-sm text-muted-foreground mt-1.5">{tier.description}</p>
                </div>

                <ul className="space-y-2.5 flex-1 mb-6">
                  {tier.features.map((f, j) => (
                    <li key={j} className="flex items-center gap-2 text-sm">
                      <Check className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                      <span className="text-foreground">{f}</span>
                    </li>
                  ))}
                </ul>

                <Button
                  variant={tier.popular ? 'default' : 'outline'}
                  className="w-full"
                  size="lg"
                >
                  {tier.cta}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── CTA Section ──────────────────────────────────────────────────────────────

export function CTASection() {
  return (
    <section className="py-20">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 text-center">
        <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-foreground mb-4">
          Ready to ship 10x faster?
        </h2>
        <p className="text-muted-foreground text-lg mb-8">
          Join 50,000+ teams already using our platform. Set up in under 5 minutes.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Button size="lg" className="h-12 px-8">
            Start for free <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
          <Button variant="outline" size="lg" className="h-12 px-8">Talk to sales</Button>
        </div>
        <p className="text-xs text-muted-foreground mt-4">No credit card required · 14-day free trial</p>
      </div>
    </section>
  )
}

// ─── Full Landing Page ────────────────────────────────────────────────────────

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground font-sans">
      <LandingNavbar />
      <HeroSection />
      <FeaturesSection />
      <TestimonialsSection />
      <PricingSection />
      <CTASection />
      <footer className="border-t border-border py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-sm text-muted-foreground">© 2025 AppName. All rights reserved.</p>
          <div className="flex gap-6 text-sm text-muted-foreground">
            {['Privacy', 'Terms', 'Cookies'].map(l => (
              <a key={l} href="#" className="hover:text-foreground transition-colors">{l}</a>
            ))}
          </div>
        </div>
      </footer>
    </div>
  )
}
