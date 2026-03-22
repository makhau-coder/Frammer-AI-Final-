/**
 * src/components/chatbot/Chatbot.jsx
 *
 * Resizable, page-aware analytics chatbot.
 *
 * SIZE MODES (toggled via buttons in header):
 *   compact   → 380 × 520px  (default — right-bottom corner)
 *   half      → 50vw × 100vh (right half of screen, full height)
 *   full      → 100vw × 100vh (full screen overlay)
 *
 * PAGE CONTEXT:
 *   Reads useLocation() to show page-specific header label, 3 suggested
 *   questions, and injects a context hint into every API call so the NLP
 *   backend knows what data the user is looking at.
 *   Resets chat history when navigating to a different page.
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import {
  MessageCircle, X, Send, Loader2,
  ChevronDown, ChevronUp, Table, BarChart2, Sparkles,
  Maximize2, Minimize2, Columns,
} from 'lucide-react';
import { Button }     from '@/components/ui/button';
import { Input }      from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { BASE_URL }   from '@/lib/api';
import ReactMarkdown  from 'react-markdown';

// ─────────────────────────────────────────────────────────────────────────────
// PAGE CONTEXT MAP  — keys match App.jsx routes EXACTLY
// ─────────────────────────────────────────────────────────────────────────────
const PAGE_CONTEXTS = {
  '/': {
    label: 'Executive Overview',
    hint:  'The user is on the Executive Overview. Platform KPIs: uploads 4,453 (+37.4% MoM), AI-generated clips 14,914 (+84.7% MoM), published clips 111 (-30% MoM), publish rate 0.74%, compute waste 99.26%, AI efficiency score 20.6/100, multiplier 3.35×, avg clips per publish 134.36×. Channel: best channel A 1.5% rate, 66.67% dead channels, Channel A 63.96% contribution. Users: top uploader Chandan, best efficiency Prithviraj 6.19%, 22 zero-value users. Language: English 1.03%, Hindi 0.33%, EN/HI 3.12×. Monthly: peak Feb 2026 2,756 clips 4.08× ratio, peak publish Apr 2025 44 clips, Dec→Feb surge 248.5%.',
    suggestions: ['What is our publish rate and why is it low?', 'Which channel is performing best?', 'Why is compute waste 99.26%?', 'Who are the top uploading users?'],
  },
  '/usage': {
    label: 'Usage & Trends',
    hint:  'The user is on Usage & Trends showing monthly time-series Mar 2025–Feb 2026: upload counts, AI-generated clip counts (peaked Feb 2026 at 2,756), published counts (peaked Apr 2025 at 44), processing hours, pipeline conversion rates (Upload→Create %, Create→Publish %), compute efficiency %, output type volumes, input type created vs published, language breakdown, statistical anomaly detection.',
    suggestions: ['Which month had the most AI-generated clips?', 'Is our publish rate improving over time?', 'What is the Upload→Create vs Create→Publish rate?', 'Which language dominates creation?'],
  },
  '/clients': {
    label: 'Client Analysis',
    hint:  'The user is on Client Analysis showing channel-by-channel and user-by-user breakdowns: videos by platform (YouTube, Instagram, Reels, LinkedIn, Shorts, X, Threads, Facebook), platform pie chart, channels processed vs published, channel publish rates, language created vs published, top 10 users by upload/publish, channel efficiency scatter, user leaderboard, full channel summary table.',
    suggestions: ['Which channel has the highest publish rate?', 'Which channel has the most compute waste?', 'Show top 10 users by upload volume', 'Which platform gets most published videos?'],
  },
  '/multi': {
    label: 'Multi-Dimensional Analysis',
    hint:  'The user is on Multi-Dimensional Analysis cross-tabulating two dimensions: Channel×User, Channel×Platform, User×Input Type, User×Platform, User×Published Status, Input Type×Platform, Input Type×Published Status. Shows stacked bar, top entities by volume, publish rate by first dimension, full heatmap.',
    suggestions: ['Which input type has the best publish rate?', 'Compare English vs Hindi performance', 'Which channel×platform combination publishes most?', 'Show User × Input Type breakdown'],
  },
  '/explorer': {
    label: 'Video Explorer',
    hint:  'The user is on Video Explorer browsing individual video records (14,918 total). Fields: video_id, headline, input_type, uploaded_by, published (bool), published_platform, published_url, ingested_at. Search by headline, filter by input type or published status, paginate 50/page, CSV export.',
    suggestions: ['How many videos are published vs unpublished?', 'Show videos published to YouTube', 'Find videos with "budget" in the headline', 'Which users uploaded the most videos?'],
  },
  '/data-quality': {
    label: 'Data Quality',
    hint:  'The user is on Data Quality showing validation check results per CSV/table. Overall quality score, pass/warn/fail counts, bar chart of scores by file, expandable per-file check cards. Key issues: team_name 99.3% unknown, 68/100 published videos missing platform, 575 duplicate headlines.',
    suggestions: ['What percentage of videos have no team assigned?', 'Which files have the most failures?', 'How many checks are passing vs failing?', 'What are the most common data quality issues?'],
  },
};

function getCtx(pathname) {
  return PAGE_CONTEXTS[pathname] || PAGE_CONTEXTS['/'];
}

// ─── Size presets ─────────────────────────────────────────────────────────────
const SIZES = {
  compact: { width: 380,    height: 520,   label: 'Compact',    icon: Minimize2 },
  half:    { width: '50vw', height: '100dvh', label: 'Half screen', icon: Columns   },
  full:    { width: '100vw',height: '100dvh', label: 'Full screen', icon: Maximize2 },
};

// ─── Message bubble components ────────────────────────────────────────────────

function ThinkingBubble() {
  return (
    <div className="mr-auto flex items-center gap-2 rounded-lg bg-secondary px-3 py-2 text-xs text-muted-foreground max-w-[90%]">
      <Loader2 className="h-3 w-3 animate-spin shrink-0" />
      Analysing your question…
    </div>
  );
}

function SqlDisclosure({ sql }) {
  const [open, setOpen] = useState(false);
  if (!sql) return null;
  return (
    <div className="mr-auto max-w-[90%] rounded-lg border border-border bg-secondary/50 text-xs overflow-hidden">
      <button
        className="flex w-full items-center justify-between px-3 py-2 text-muted-foreground hover:text-foreground"
        onClick={() => setOpen(o => !o)}
      >
        <span className="font-mono text-[10px]">SQL generated</span>
        {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>
      {open && (
        <pre className="overflow-x-auto px-3 pb-3 text-[10px] font-mono text-foreground/80 whitespace-pre-wrap">
          {sql}
        </pre>
      )}
    </div>
  );
}

function DataTable({ rows }) {
  const [showTable, setShowTable] = useState(false);
  if (!rows || rows.length === 0) return null;
  const cols    = Object.keys(rows[0]);
  const preview = rows.slice(0, 15);
  return (
    <div className="mr-auto max-w-[90%] rounded-lg border border-border bg-secondary/50 text-xs overflow-hidden">
      <button
        className="flex w-full items-center justify-between px-3 py-2 text-muted-foreground hover:text-foreground"
        onClick={() => setShowTable(o => !o)}
      >
        <span className="flex items-center gap-1">
          <Table className="h-3 w-3" />
          {rows.length} row{rows.length !== 1 ? 's' : ''} returned
        </span>
        {showTable ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>
      {showTable && (
        <div className="overflow-x-auto px-3 pb-3 max-h-64">
          <table className="min-w-full text-[10px]">
            <thead>
              <tr>
                {cols.map(c => (
                  <th key={c} className="border-b border-border py-1 pr-4 text-left font-semibold text-muted-foreground sticky top-0 bg-secondary/80">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.map((row, i) => (
                <tr key={i} className={i % 2 ? 'bg-muted/10' : ''}>
                  {cols.map(c => (
                    <td key={c} className="py-1 pr-4 text-foreground/80">
                      {String(row[c] ?? '')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length > 15 && (
            <p className="pt-1 text-[10px] text-muted-foreground">… and {rows.length - 15} more rows</p>
          )}
        </div>
      )}
    </div>
  );
}

function ChartImage({ chartUrl, chartType }) {
  if (!chartUrl) return null;
  const API = (BASE_URL || 'http://localhost:8000');
  return (
    <div className="mr-auto overflow-hidden rounded-lg border border-border bg-secondary/50 max-w-[90%]">
      <div className="px-3 pt-2 text-[10px] text-muted-foreground capitalize flex items-center gap-1">
        <BarChart2 className="h-3 w-3" />{chartType || 'chart'}
      </div>
      <img
        src={`${API}${chartUrl}`}
        alt={chartType || 'chart'}
        className="w-full object-contain rounded-b-lg"
        style={{ maxHeight: 260 }}
        onError={e => { e.currentTarget.closest('.rounded-lg').style.display = 'none'; }}
      />
    </div>
  );
}

function InsightBubble({ insight }) {
  if (!insight) return null;
  return (
    <div className="mr-auto max-w-[90%] rounded-lg bg-secondary px-3 py-2.5 text-xs text-secondary-foreground">
      <div className="prose prose-xs prose-invert max-w-none
        prose-p:text-secondary-foreground prose-p:leading-relaxed prose-p:my-1 prose-p:text-xs
        prose-strong:text-foreground prose-strong:font-semibold
        prose-ul:my-1 prose-ul:pl-3.5 prose-li:my-0.5 prose-li:text-xs prose-li:text-secondary-foreground
        prose-ol:my-1 prose-ol:pl-3.5
        prose-h3:text-xs prose-h3:font-semibold prose-h3:text-foreground prose-h3:mt-2 prose-h3:mb-0.5
        prose-code:text-indigo-300 prose-code:bg-muted/40 prose-code:px-0.5 prose-code:rounded prose-code:text-[11px]">
        <ReactMarkdown>{insight}</ReactMarkdown>
      </div>
    </div>
  );
}

function ErrorBubble({ message }) {
  return (
    <div className="mr-auto max-w-[90%] rounded-lg bg-destructive/10 border border-destructive/20 px-3 py-2 text-xs text-destructive whitespace-pre-wrap">
      {message}
    </div>
  );
}

// ─── Welcome message ──────────────────────────────────────────────────────────
function makeWelcome(ctx) {
  return {
    id: 'init', role: 'bot',
    parts: [{
      type: 'insight',
      content: `Hi! I'm your **${ctx.label}** assistant.\n\nI know the data on this page and can answer questions about it.\n\nTry asking:\n${ctx.suggestions.slice(0, 3).map(s => `• "${s}"`).join('\n')}`,
    }],
  };
}

// ─── Main component ───────────────────────────────────────────────────────────
export function Chatbot() {
  const { pathname } = useLocation();
  const ctx          = getCtx(pathname);
  const prevPath     = useRef(pathname);

  const [open,      setOpen]      = useState(false);
  const [sizeMode,  setSizeMode]  = useState('compact'); // 'compact' | 'half' | 'full'
  const [input,     setInput]     = useState('');
  const [streaming, setStreaming] = useState(false);
  const [messages,  setMessages]  = useState(() => [makeWelcome(ctx)]);

  const bottomRef = useRef(null);
  const esRef     = useRef(null);
  const inputRef  = useRef(null);

  // ── Reset when navigating to a new page ──────────────────────────
  useEffect(() => {
    if (pathname !== prevPath.current) {
      prevPath.current = pathname;
      const newCtx = getCtx(pathname);
      esRef.current?.close();
      setStreaming(false);
      setInput('');
      setMessages([makeWelcome(newCtx)]);
    }
  }, [pathname]);

  // ── Auto-scroll ───────────────────────────────────────────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const addBotPart = useCallback((msgId, part) => {
    setMessages(prev => prev.map(m => {
      if (m.id !== msgId) return m;
      return { ...m, parts: [...m.parts, part] };
    }));
  }, []);

  // ── Send ──────────────────────────────────────────────────────────
  const send = useCallback((questionOverride) => {
    const rawQuestion = (questionOverride ?? input).trim();
    if (!rawQuestion || streaming) return;

    setInput('');
    setStreaming(true);

    const userMsgId = `u-${Date.now()}`;
    const botMsgId  = `b-${Date.now()}`;

    setMessages(prev => [
      ...prev,
      { id: userMsgId, role: 'user', parts: [{ type: 'text', content: rawQuestion }] },
      { id: botMsgId,  role: 'bot',  parts: [{ type: 'thinking' }] },
    ]);

    const currentCtx      = getCtx(pathname);
    const questionWithCtx = `[Page context: ${currentCtx.hint}]\n\nUser question: ${rawQuestion}`;
    const sessionId = `ss-${Date.now()}`;
    const url = `${BASE_URL}/api/chat/stream?question=${encodeURIComponent(questionWithCtx)}&session_id=${sessionId}`;
    const es  = new EventSource(url);
    esRef.current = es;

    let thinkingRemoved = false;
    const removeThinking = () => {
      if (thinkingRemoved) return;
      thinkingRemoved = true;
      setMessages(prev => prev.map(m => {
        if (m.id !== botMsgId) return m;
        return { ...m, parts: m.parts.filter(p => p.type !== 'thinking') };
      }));
    };

    es.addEventListener('sql_ready',     e => { removeThinking(); const { sql } = JSON.parse(e.data); addBotPart(botMsgId, { type: 'sql', content: sql }); });
    es.addEventListener('data_ready',    e => { removeThinking(); const { rows, row_count } = JSON.parse(e.data); addBotPart(botMsgId, { type: 'table', rows, row_count }); });
    es.addEventListener('insight_ready', e => { removeThinking(); const { insight } = JSON.parse(e.data); addBotPart(botMsgId, { type: 'insight', content: insight }); });
    es.addEventListener('chart_ready',   e => { removeThinking(); const { chart_url, chart_type } = JSON.parse(e.data); addBotPart(botMsgId, { type: 'chart', chartUrl: chart_url, chartType: chart_type }); });
    es.addEventListener('error',         e => { removeThinking(); const data = JSON.parse(e.data || '{}'); addBotPart(botMsgId, { type: 'error', content: data.message || 'Something went wrong.' }); });
    es.addEventListener('done', () => { es.close(); setStreaming(false); inputRef.current?.focus(); });
    es.onerror = () => { removeThinking(); addBotPart(botMsgId, { type: 'error', content: 'Connection lost. Please try again.' }); es.close(); setStreaming(false); };
  }, [input, streaming, addBotPart, pathname]);

  useEffect(() => () => esRef.current?.close(), []);

  // ── Size styles ───────────────────────────────────────────────────
  const sizeStyle = () => {
    if (sizeMode === 'half') {
      return {
        right: 0, bottom: 0, top: 0,
        width: 'max(50vw, min(100vw, 400px))',
        maxWidth: '720px',
        height: '100dvh',
        borderRadius: '0',
      };
    }
    if (sizeMode === 'full') {
      return {
        right: 0, bottom: 0, top: 0, left: 0,
        width: '100vw',
        height: '100dvh',
        borderRadius: '0',
      };
    }
    // compact
    return { 
      width: 'min(380px, calc(100vw - 32px))', 
      height: 'min(520px, calc(100dvh - 32px))', 
      bottom: '16px', 
      right: '16px', 
      borderRadius: '12px' 
    };
  };

  // ── Closed: floating button ───────────────────────────────────────
  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        title={`Ask about ${ctx.label}`}
        className="fixed bottom-4 right-4 md:bottom-6 md:right-6 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg hover:opacity-90 transition-opacity"
      >
        <MessageCircle className="h-5 w-5" />
      </button>
    );
  }

  // ── Open: chat panel ──────────────────────────────────────────────
  return (
    <div
      className="fixed z-50 flex flex-col border border-border bg-card shadow-2xl overflow-hidden"
      style={{ ...sizeStyle(), transition: 'width 0.25s ease, height 0.25s ease' }}
    >
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 border-b border-border px-4 py-3 shrink-0 bg-card/95 backdrop-blur-sm">

        {/* Icon + page name */}
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <Sparkles className="h-3.5 w-3.5 shrink-0 text-indigo-400" />
          <div className="min-w-0">
            <p className="text-sm font-semibold text-foreground leading-none">Analytics Assistant</p>
            <p className="text-[10px] text-muted-foreground mt-0.5 truncate">{ctx.label} context</p>
          </div>
        </div>

        {/* Size controls */}
        <div className="flex items-center gap-1 shrink-0">
          {/* Compact */}
          <button
            onClick={() => setSizeMode('compact')}
            title="Compact"
            className={`flex h-6 w-6 items-center justify-center rounded transition-colors ${sizeMode === 'compact' ? 'bg-primary/20 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted/40'}`}
          >
            <Minimize2 className="h-3.5 w-3.5" />
          </button>
          {/* Half screen */}
          <button
            onClick={() => setSizeMode('half')}
            title="Half screen"
            className={`flex h-6 w-6 items-center justify-center rounded transition-colors ${sizeMode === 'half' ? 'bg-primary/20 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted/40'}`}
          >
            <Columns className="h-3.5 w-3.5" />
          </button>
          {/* Full screen */}
          <button
            onClick={() => setSizeMode('full')}
            title="Full screen"
            className={`flex h-6 w-6 items-center justify-center rounded transition-colors ${sizeMode === 'full' ? 'bg-primary/20 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted/40'}`}
          >
            <Maximize2 className="h-3.5 w-3.5" />
          </button>

          <div className="w-px h-4 bg-border mx-1" />

          {/* Close */}
          <button
            onClick={() => setOpen(false)}
            className="text-muted-foreground hover:text-foreground transition-colors"
            title="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* ── Suggestions (only at start of conversation) ─────────────── */}
      {messages.length <= 1 && (
        <div className="border-b border-border/50 px-4 py-2.5 shrink-0 bg-muted/10">
          <p className="text-[10px] text-muted-foreground mb-1.5">Suggested for this page:</p>
          <div className={`grid gap-1.5 ${sizeMode === 'compact' ? 'grid-cols-1' : 'grid-cols-1 sm:grid-cols-2'}`}>
            {ctx.suggestions.map((s, i) => (
              <button
                key={i}
                onClick={() => send(s)}
                className="text-left text-[10px] px-2.5 py-1.5 rounded-lg bg-muted/40 hover:bg-primary/10 hover:text-primary border border-border/40 hover:border-primary/30 text-muted-foreground transition-colors truncate"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Messages ─────────────────────────────────────────────────── */}
      <ScrollArea className="flex-1 p-4">
        <div className={`flex flex-col gap-3 ${sizeMode !== 'compact' ? 'max-w-3xl mx-auto' : ''}`}>
          {messages.map(msg => (
            <div
              key={msg.id}
              className={`flex flex-col gap-2 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
            >
              {msg.parts.map((part, i) => {
                if (msg.role === 'user') {
                  return (
                    <div key={i} className={`rounded-lg bg-primary px-3 py-2 text-xs text-primary-foreground ${sizeMode === 'compact' ? 'max-w-[85%]' : 'max-w-2xl'}`}>
                      {part.content}
                    </div>
                  );
                }
                const maxW = sizeMode === 'compact' ? 'max-w-[90%]' : 'max-w-2xl w-full';
                switch (part.type) {
                  case 'thinking': return <ThinkingBubble key={i} />;
                  case 'sql':      return <div key={i} className={maxW}><SqlDisclosure sql={part.content} /></div>;
                  case 'table':    return <div key={i} className={maxW}><DataTable rows={part.rows} /></div>;
                  case 'insight':  return <div key={i} className={maxW}><InsightBubble insight={part.content} /></div>;
                  case 'chart':    return <div key={i} className={maxW}><ChartImage chartUrl={part.chartUrl} chartType={part.chartType} /></div>;
                  case 'error':    return <div key={i} className={maxW}><ErrorBubble message={part.content} /></div>;
                  default:         return null;
                }
              })}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      {/* ── Input ────────────────────────────────────────────────────── */}
      <div className={`border-t border-border p-3 shrink-0 bg-card/95 ${sizeMode !== 'compact' ? 'md:px-6 md:py-4' : ''}`}>
        <div className={`flex items-center gap-2 ${sizeMode !== 'compact' ? 'max-w-3xl mx-auto' : ''}`}>
          <Input
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
            placeholder={`Ask about ${ctx.label}…`}
            className={sizeMode === 'compact' ? 'h-8 text-xs' : 'h-10 text-sm'}
            disabled={streaming}
          />
          <Button
            size="icon"
            className={sizeMode === 'compact' ? 'h-8 w-8 shrink-0' : 'h-10 w-10 shrink-0'}
            onClick={() => send()}
            disabled={streaming || !input.trim()}
          >
            {streaming
              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
              : <Send    className="h-3.5 w-3.5" />}
          </Button>
        </div>
        {sizeMode !== 'compact' && (
          <p className="text-center text-[10px] text-muted-foreground/40 mt-2">
            Enter to send · Shift+Enter for new line
          </p>
        )}
      </div>
    </div>
  );
}
