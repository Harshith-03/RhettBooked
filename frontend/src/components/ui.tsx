import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { usePrefersReducedMotion } from "../theme";

export function money(n: number): string {
  return `$${Math.round(n).toLocaleString()}`;
}

// --- Section card: --card bg, 1px border, radius 12, optional 3px red top border.
export function SectionCard({
  children,
  topBorder = true,
  className = "",
}: {
  children: ReactNode;
  topBorder?: boolean;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl ${className}`}
      style={{
        background: "var(--card)",
        border: "1px solid var(--border)",
        borderTop: topBorder ? "3px solid var(--red)" : "1px solid var(--border)",
        padding: 20,
      }}
    >
      {children}
    </div>
  );
}

// --- Status pill: colour AND text.
const PILL = {
  ok: { bg: "var(--ok-bg)", fg: "var(--ok-text)", label: "✓ ok" },
  strained: { bg: "var(--warn-bg)", fg: "var(--warn-text)", label: "! strained" },
  failing: { bg: "var(--red)", fg: "#ffffff", label: "× failing" },
  curated: { bg: "var(--card-alt)", fg: "var(--muted)", label: "◆ curated" },
  "coming soon": { bg: "var(--card-alt)", fg: "var(--muted)", label: "coming soon" },
} as const;

export function StatusPill({ status }: { status: string }) {
  const p = (PILL as any)[status] ?? PILL["coming soon"];
  return (
    <span
      className="inline-block rounded-full px-2 py-0.5"
      style={{ background: p.bg, color: p.fg, fontSize: 11, fontWeight: 600 }}
    >
      {p.label}
    </span>
  );
}

// --- Caps label + big tabular number + muted subline.
export function Stat({
  label,
  value,
  sub,
  valueClass = "",
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  valueClass?: string;
}) {
  return (
    <div>
      <p className="caps-label">{label}</p>
      <p className={`big-number mt-1 ${valueClass}`} style={{ color: "var(--text)" }}>
        {value}
      </p>
      {sub ? (
        <p className="mt-0.5 text-xs" style={{ color: "var(--muted)" }}>
          {sub}
        </p>
      ) : null}
    </div>
  );
}

// --- Count-up number (rAF, ~400ms), honours reduced motion.
export function CountUp({ value, suffix = "" }: { value: number; suffix?: string }) {
  const reduced = usePrefersReducedMotion();
  const [display, setDisplay] = useState(reduced ? value : 0);
  const prev = useRef(0);
  useEffect(() => {
    if (reduced) {
      setDisplay(value);
      return;
    }
    const from = prev.current;
    const to = value;
    const start = performance.now();
    const dur = 400;
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / dur);
      setDisplay(Math.round(from + (to - from) * t));
      if (t < 1) raf = requestAnimationFrame(tick);
      else prev.current = to;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, reduced]);
  return (
    <span style={{ fontVariantNumeric: "tabular-nums" }}>
      {display.toLocaleString()}
      {suffix}
    </span>
  );
}

// --- Collapsible drawer with animated height + opacity and a rotating arrow.
export function Drawer({
  label = "Show details",
  defaultOpen = false,
  children,
}: {
  label?: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const reduced = usePrefersReducedMotion();
  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="mt-2 inline-flex items-center gap-1 text-sm font-medium"
        style={{ color: "var(--red-text)" }}
      >
        {open ? "Hide details" : label}
        <motion.span
          animate={{ rotate: open ? 90 : 0 }}
          transition={{ duration: reduced ? 0 : 0.22 }}
          aria-hidden
        >
          →
        </motion.span>
      </button>
      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: reduced ? 0 : 0.22, ease: "easeOut" }}
            style={{ overflow: "hidden" }}
          >
            <div
              className="mt-3 border-t pt-3"
              style={{ borderColor: "var(--border)" }}
            >
              {children}
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

// --- Buttons + chip.
export function PrimaryButton(props: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const reduced = usePrefersReducedMotion();
  return (
    <motion.button
      whileTap={reduced ? undefined : { scale: 0.98 }}
      transition={{ duration: 0.12 }}
      {...(props as any)}
      className="rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
      style={{ background: "var(--red)" }}
    />
  );
}

export function SecondaryButton(props: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const reduced = usePrefersReducedMotion();
  return (
    <motion.button
      whileTap={reduced ? undefined : { scale: 0.98 }}
      transition={{ duration: 0.12 }}
      {...(props as any)}
      className="rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-50"
      style={{ background: "transparent", color: "var(--text)", border: "1px solid var(--text)" }}
    />
  );
}

export function Chip({ label, active, onClick }: { label: string; active?: boolean; onClick?: () => void }) {
  const reduced = usePrefersReducedMotion();
  return (
    <motion.button
      whileTap={reduced ? undefined : { scale: 0.98 }}
      onClick={onClick}
      className="rounded-full px-3 py-1 text-xs font-medium"
      style={{
        border: "1px solid var(--border)",
        background: active ? "var(--red-soft)" : "transparent",
        color: active ? "var(--red-text)" : "var(--text)",
      }}
    >
      {label}
    </motion.button>
  );
}

export function Skeleton({ height = 80 }: { height?: number }) {
  return (
    <div
      className="animate-pulse rounded-xl"
      style={{ background: "var(--card-alt)", border: "1px solid var(--border)", height }}
    />
  );
}

// --- Page-load stagger container + item.
export function Stagger({ children }: { children: ReactNode }) {
  const reduced = usePrefersReducedMotion();
  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={{ show: { transition: { staggerChildren: reduced ? 0 : 0.06 } } }}
      className="space-y-4"
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({ children }: { children: ReactNode }) {
  const reduced = usePrefersReducedMotion();
  return (
    <motion.div
      variants={{
        hidden: { opacity: 0, y: reduced ? 0 : 8 },
        show: { opacity: 1, y: 0, transition: { duration: 0.25, ease: "easeOut" } },
      }}
    >
      {children}
    </motion.div>
  );
}

// --- v2 aesthetic primitives -------------------------------------------------

// A card that lifts slightly on hover with a soft shadow (Apple-style).
export function HoverCard({
  children,
  className = "",
  style = {},
  topAccent = false,
}: {
  children: ReactNode;
  className?: string;
  style?: React.CSSProperties;
  topAccent?: boolean;
}) {
  const reduced = usePrefersReducedMotion();
  return (
    <motion.div
      whileHover={reduced ? undefined : { y: -3 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className={`rounded-2xl ${className}`}
      style={{
        background: "var(--card)",
        border: "1px solid var(--border)",
        borderTop: topAccent ? "3px solid var(--red)" : undefined,
        boxShadow: "var(--shadow-sm)",
        padding: 22,
        ...style,
      }}
    >
      {children}
    </motion.div>
  );
}

// Reveal on scroll: fade + rise once when it enters the viewport.
export function Reveal({
  children,
  delay = 0,
}: {
  children: ReactNode;
  delay?: number;
}) {
  const reduced = usePrefersReducedMotion();
  return (
    <motion.div
      initial={{ opacity: 0, y: reduced ? 0 : 14 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: reduced ? 0 : 0.4, ease: [0.22, 1, 0.36, 1], delay: reduced ? 0 : delay }}
    >
      {children}
    </motion.div>
  );
}

// A subtle animated label-value stat used in the restyled detail cards.
export function GridStat({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: ReactNode;
  accent?: boolean;
}) {
  return (
    <div className="rounded-xl px-3 py-3" style={{ background: "var(--card-alt)" }}>
      <p className="caps-label">{label}</p>
      <p
        className="mt-1 tnum"
        style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.02em", color: accent ? "var(--red-text)" : "var(--text)" }}
      >
        {value}
      </p>
    </div>
  );
}
