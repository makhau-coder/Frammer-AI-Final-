/**
 * src/components/chatbot/Chatbot.jsx
 *
 * Floating chatbot widget that connects to the real backend.
 * Uses GET /api/chat/stream (SSE) for live streaming responses.
 *
 * Features:
 *  - Progressive streaming: shows thinking → SQL → data → insight → chart
 *  - Plotly chart rendering (install: npm install react-plotly.js plotly.js-dist-min)
 *  - Data table for query results
 *  - SQL disclosure (shows what query ran)
 *  - Explainability: shows which tables/filters were applied
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { MessageCircle, X, Send, Loader2, ChevronDown, ChevronUp, Table, BarChart2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { BASE_URL } from '@/lib/api';

// Lazy load Plotly to avoid massive bundle on pages that don't use it
let PlotlyComponent = null;

async function loadPlotly() {
  if (PlotlyComponent) return PlotlyComponent;
  try {
    const Plotly = await import('react-plotly.js');
    PlotlyComponent = Plotly.default;
    return PlotlyComponent;
  } catch {
    return null;
  }
}

// ─── Message types ────────────────────────────────────────────────────────────

function ThinkingBubble() {
  return (
    <div className="mr-auto flex items-center gap-2 rounded-lg bg-secondary px-3 py-2 text-xs text-muted-foreground max-w-[90%]">
      <Loader2 className="h-3 w-3 animate-spin" />
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
  const cols = Object.keys(rows[0]);
  const preview = rows.slice(0, 10);

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
        <div className="overflow-x-auto px-3 pb-3">
          <table className="min-w-full text-[10px]">
            <thead>
              <tr>
                {cols.map(c => (
                  <th key={c} className="border-b border-border py-1 pr-4 text-left font-semibold text-muted-foreground">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.map((row, i) => (
                <tr key={i}>
                  {cols.map(c => (
                    <td key={c} className="py-1 pr-4 text-foreground/80">
                      {String(row[c] ?? '')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length > 10 && (
            <p className="pt-1 text-[10px] text-muted-foreground">
              … and {rows.length - 10} more rows
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function PlotlyChart({ chartJson, chartType }) {
  const [Plot, setPlot] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    loadPlotly().then(p => {
      if (p) setPlot(() => p);
      else setError(true);
    });
  }, []);

  if (error) {
    return (
      <div className="mr-auto max-w-[90%] rounded-lg border border-border bg-secondary/50 px-3 py-2 text-xs text-muted-foreground">
        <BarChart2 className="inline h-3 w-3 mr-1" />
        Chart ready. Run{' '}
        <code className="font-mono">npm install react-plotly.js plotly.js-dist-min</code>{' '}
        to render it.
      </div>
    );
  }

  if (!Plot || !chartJson) return null;

  // Compact layout for the chat widget
  const layout = {
    ...chartJson.layout,
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    font: { color: '#e0e0e0', size: 10 },
    margin: { l: 40, r: 10, t: 30, b: 40 },
    height: 220,
    width: 270,
    showlegend: false,
    autosize: false,
  };

  return (
    <div className="mr-auto overflow-hidden rounded-lg border border-border bg-secondary/50">
      <div className="px-3 pt-2 text-[10px] text-muted-foreground capitalize">
        <BarChart2 className="inline h-3 w-3 mr-1" />
        {chartType} chart
      </div>
      <Plot
        data={chartJson.data}
        layout={layout}
        config={{ displayModeBar: false, responsive: false }}
      />
    </div>
  );
}

function InsightBubble({ insight }) {
  if (!insight) return null;
  return (
    <div className="mr-auto max-w-[90%] rounded-lg bg-secondary px-3 py-2 text-xs leading-relaxed text-secondary-foreground whitespace-pre-wrap">
      {insight}
    </div>
  );
}

function ErrorBubble({ message }) {
  return (
    <div className="mr-auto max-w-[90%] rounded-lg bg-destructive/10 border border-destructive/20 px-3 py-2 text-xs text-destructive">
      {message}
    </div>
  );
}

// ─── Main chatbot component ───────────────────────────────────────────────────

export function Chatbot() {
  const [open, setOpen]       = useState(false);
  const [input, setInput]     = useState('');
  const [streaming, setStreaming] = useState(false);
  const [messages, setMessages]  = useState([
    {
      id: 'init',
      role: 'bot',
      parts: [{ type: 'insight', content: 'Hi! Ask me anything about your video analytics.\n\nExamples:\n• "Which channel has the highest publish rate?"\n• "Show me monthly upload trends"\n• "Which users process the most content?"' }],
    },
  ]);

  const bottomRef  = useRef(null);
  const esRef      = useRef(null);
  const inputRef   = useRef(null);

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const addBotPart = useCallback((msgId, part) => {
    setMessages(prev => prev.map(m => {
      if (m.id !== msgId) return m;
      return { ...m, parts: [...m.parts, part] };
    }));
  }, []);

  const send = useCallback(() => {
    const question = input.trim();
    if (!question || streaming) return;

    setInput('');
    setStreaming(true);

    const userMsgId = `u-${Date.now()}`;
    const botMsgId  = `b-${Date.now()}`;

    setMessages(prev => [
      ...prev,
      { id: userMsgId, role: 'user', parts: [{ type: 'text', content: question }] },
      { id: botMsgId,  role: 'bot',  parts: [{ type: 'thinking' }] },
    ]);

    const url = `${BASE_URL}/api/chat/stream?question=${encodeURIComponent(question)}`;
    const es  = new EventSource(url);
    esRef.current = es;

    // Remove thinking bubble on first real event
    let thinkingRemoved = false;
    const removeThinking = () => {
      if (thinkingRemoved) return;
      thinkingRemoved = true;
      setMessages(prev => prev.map(m => {
        if (m.id !== botMsgId) return m;
        return { ...m, parts: m.parts.filter(p => p.type !== 'thinking') };
      }));
    };

    es.addEventListener('sql_ready', e => {
      removeThinking();
      const { sql } = JSON.parse(e.data);
      addBotPart(botMsgId, { type: 'sql', content: sql });
    });

    es.addEventListener('data_ready', e => {
      removeThinking();
      const { rows, row_count } = JSON.parse(e.data);
      addBotPart(botMsgId, { type: 'table', rows, row_count });
    });

    es.addEventListener('insight_ready', e => {
      removeThinking();
      const { insight } = JSON.parse(e.data);
      addBotPart(botMsgId, { type: 'insight', content: insight });
    });

    es.addEventListener('chart_ready', e => {
      removeThinking();
      const { chart_json, chart_type } = JSON.parse(e.data);
      addBotPart(botMsgId, { type: 'chart', chartJson: chart_json, chartType: chart_type });
    });

    es.addEventListener('error', e => {
      removeThinking();
      const data = JSON.parse(e.data || '{}');
      addBotPart(botMsgId, { type: 'error', content: data.message || 'Something went wrong.' });
    });

    es.addEventListener('done', () => {
      es.close();
      setStreaming(false);
      inputRef.current?.focus();
    });

    // Network error / timeout
    es.onerror = () => {
      removeThinking();
      addBotPart(botMsgId, { type: 'error', content: 'Connection lost. Please try again.' });
      es.close();
      setStreaming(false);
    };
  }, [input, streaming, addBotPart]);

  // Cleanup EventSource on unmount
  useEffect(() => () => esRef.current?.close(), []);

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg hover:opacity-90 transition-opacity"
      >
        <MessageCircle className="h-5 w-5" />
      </button>
    );
  }

  return (
    <div
      className="fixed bottom-6 right-6 z-50 flex flex-col rounded-lg border border-border bg-card shadow-2xl"
      style={{ width: 320, height: 480 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <span className="text-sm font-semibold text-foreground">Analytics Assistant</span>
        <button onClick={() => setOpen(false)} className="text-muted-foreground hover:text-foreground">
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1 p-3">
        <div className="flex flex-col gap-3">
          {messages.map(msg => (
            <div key={msg.id} className={`flex flex-col gap-2 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
              {msg.parts.map((part, i) => {
                if (msg.role === 'user') {
                  return (
                    <div key={i} className="ml-auto max-w-[85%] rounded-lg bg-primary px-3 py-2 text-xs text-primary-foreground">
                      {part.content}
                    </div>
                  );
                }
                switch (part.type) {
                  case 'thinking': return <ThinkingBubble key={i} />;
                  case 'sql':     return <SqlDisclosure   key={i} sql={part.content} />;
                  case 'table':   return <DataTable       key={i} rows={part.rows} />;
                  case 'insight': return <InsightBubble   key={i} insight={part.content} />;
                  case 'chart':   return <PlotlyChart     key={i} chartJson={part.chartJson} chartType={part.chartType} />;
                  case 'error':   return <ErrorBubble     key={i} message={part.content} />;
                  default:        return null;
                }
              })}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="flex items-center gap-2 border-t border-border p-3">
        <Input
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
          placeholder="Ask a question…"
          className="h-8 text-xs"
          disabled={streaming}
        />
        <Button size="icon" className="h-8 w-8 shrink-0" onClick={send} disabled={streaming || !input.trim()}>
          {streaming ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
        </Button>
      </div>
    </div>
  );
}
