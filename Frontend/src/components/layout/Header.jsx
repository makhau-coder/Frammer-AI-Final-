import { SidebarTrigger } from '@/components/ui/sidebar';
import { Bell, TrendingUp, TrendingDown, Minus, ChevronRight, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useState, useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import { BASE_URL } from '@/lib/api';

// ─── Live clock ───────────────────────────────────────────────────────
function LiveClock() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const dateStr = time.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
  const timeStr = time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });

  return (
    <div className="hidden lg:flex items-center gap-2 text-xs text-muted-foreground/60 font-mono tabular-nums select-none border-r border-border/40 pr-4 mr-1">
      <Clock className="h-3 w-3 shrink-0" />
      <span>{dateStr}</span>
      <span className="opacity-40">·</span>
      <span>{timeStr}</span>
    </div>
  );
}

// ─── KPI Ticker ───────────────────────────────────────────────────────
function KpiTicker() {
  const { data: monthlyData = [] } = useQuery({
    queryKey: ['monthlyData'],
    queryFn: async () => {
      const res = await fetch(`${BASE_URL || "http://localhost:8000"}/api/monthly`);
      if (!res.ok) return [];
      const data = await res.json();
      return Array.isArray(data)
        ? data.filter(m => (m.uploaded_count || 0) > 0 || (m.created_count || 0) > 0)
        : [];
    },
    staleTime: 60000,
  });

  const [idx, setIdx] = useState(0);

  const metrics = useMemo(() => {
    if (!monthlyData.length) return [];
    const curr = monthlyData[monthlyData.length - 1] || {};
    const prev = monthlyData[monthlyData.length - 2] || {};
    const pct = (c, p) => (p > 0 ? (((c || 0) - p) / p) * 100 : 0);

    return [
      { label: 'Uploads', value: curr.uploaded_count || 0, delta: pct(curr.uploaded_count, prev.uploaded_count) },
      { label: 'Created', value: curr.created_count || 0, delta: pct(curr.created_count, prev.created_count) },
      { label: 'Published', value: curr.published_count || 0, delta: pct(curr.published_count, prev.published_count) },
    ].filter(m => m.value > 0);
  }, [monthlyData]);

  useEffect(() => {
    if (metrics.length <= 1) return;
    const t = setInterval(() => setIdx(i => (i + 1) % metrics.length), 5000);
    return () => clearInterval(t);
  }, [metrics.length]);

  if (!metrics.length) {
    return (
      <div className="hidden min-[1100px]:flex items-center gap-2 px-3 py-1.5 rounded-full bg-muted/40 border border-border/30 text-[11px] text-muted-foreground/50 select-none">
        <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/30 animate-pulse" />
        Loading metrics…
      </div>
    );
  }

  const m = metrics[idx];
  const up = m.delta > 0.5;
  const down = m.delta < -0.5;
  const flat = !up && !down;

  return (
    <div className="hidden min-[1100px]:flex items-center select-none">
      <AnimatePresence mode="wait">
        <motion.div
          key={idx}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.3 }}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-full border text-[11px] font-medium tracking-wide ${up ? 'bg-emerald-500/8 border-emerald-500/20 text-emerald-400'
            : down ? 'bg-red-500/8 border-red-500/20 text-red-400'
              : 'bg-muted/40 border-border/30 text-muted-foreground/60'
            }`}
        >
          {up && <TrendingUp className="h-3 w-3 shrink-0" />}
          {down && <TrendingDown className="h-3 w-3 shrink-0" />}
          {flat && <Minus className="h-3 w-3 shrink-0 opacity-50" />}

          <span>{m.label}</span>
          <span className="opacity-40">·</span>
          <span className="font-mono tabular-nums">{m.value.toLocaleString()}</span>

          {!flat && (
            <>
              <span className="opacity-40">·</span>
              <span className="font-mono tabular-nums">
                {m.delta > 0 ? '+' : ''}{m.delta.toFixed(1)}%
              </span>
            </>
          )}

          <span className="opacity-25 text-[10px]">vs last month</span>

          {/* Dot pagination */}
          {metrics.length > 1 && (
            <div className="flex items-center gap-0.5 ml-0.5">
              {metrics.map((_, i) => (
                <span key={i}
                  className={`h-1 rounded-full transition-all ${i === idx ? 'w-3 bg-current' : 'w-1 bg-current opacity-25'}`}
                />
              ))}
            </div>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

// ─── Notification bell with badge ────────────────────────────────────
function NotificationBell() {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(v => !v)}
        className="relative flex h-8 w-8 items-center justify-center rounded-xl border border-border/40 bg-card/60 text-muted-foreground hover:text-foreground hover:border-border hover:bg-card transition-all duration-150"
      >
        <Bell className="h-3.5 w-3.5" />
        {/* Red dot badge */}
        <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 rounded-full bg-primary ring-1 ring-background" />
      </button>
    </div>
  );
}

// ─── User avatar with initials ────────────────────────────────────────
function UserMenu() {
  return (
    <button className="flex items-center gap-2 rounded-xl border border-border/40 bg-card/60 pl-1 pr-2.5 py-1 hover:border-border hover:bg-card transition-all duration-150 group">
      <Avatar className="h-6 w-6 shrink-0">
        <AvatarFallback className="bg-primary text-primary-foreground text-[10px] font-bold">
          FA
        </AvatarFallback>
      </Avatar>
      <div className="hidden sm:flex flex-col items-start leading-none">
        <span className="text-[11px] font-semibold text-foreground">Frammer AI</span>
        <span className="text-[10px] text-muted-foreground/60">Admin</span>
      </div>
    </button>
  );
}

// ─── Separator ───────────────────────────────────────────────────────
function Sep() {
  return <div className="h-5 w-px bg-border/40 mx-0.5 shrink-0" />;
}

// ─── Page title with subtle breadcrumb accent ─────────────────────────
function PageTitle({ title }) {
  return (
    <div className="flex items-center gap-2.5 min-w-0">
      {/* Accent bar */}
      <div className="h-5 w-0.5 rounded-full bg-primary shrink-0 opacity-80" />
      <h1 className="text-sm font-semibold text-foreground truncate tracking-tight">
        {title}
      </h1>
    </div>
  );
}

// ─── Main Header ─────────────────────────────────────────────────────
export function Header({ title }) {
  return (
    <header className="sticky top-0 z-20">
      {/* Glassmorphism + subtle bottom border */}
      <div className="relative flex h-12 items-center gap-3 px-3 bg-background/80 backdrop-blur-md border-b border-border/50">

        {/* Subtle gradient overlay for depth */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: 'linear-gradient(90deg, hsl(var(--primary)/0.04) 0%, transparent 40%)',
          }}
        />

        {/* Left group */}
        <div className="relative flex items-center gap-2 shrink-0">
          <SidebarTrigger className="h-7 w-7 rounded-lg border border-border/40 bg-card/50 text-muted-foreground hover:text-foreground hover:bg-card hover:border-border transition-all duration-150 flex items-center justify-center shrink-0" />
          <Sep />
          <PageTitle title={title} />
        </div>

        {/* Spacer */}
        <div className="flex-1 min-w-0" />

        {/* Right group */}
        <div className="relative flex items-center gap-2 shrink-0">
          <LiveClock />
          <KpiTicker />
          <Sep />
          <NotificationBell />
          <UserMenu />
        </div>

      </div>
    </header>
  );
}
