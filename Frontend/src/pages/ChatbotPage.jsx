/**
 * src/pages/ChatbotPage.jsx
 *
 * Full-page NLQ chatbot interface.
 * Uses the SSE streaming endpoint GET /api/chat/stream
 * for real-time progressive responses.
 *
 * Requires: npm install react-plotly.js plotly.js-dist-min
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import {
  Send, Loader2, ChevronDown, ChevronUp,
  Table, BarChart2, Sparkles, RotateCcw
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { BASE_URL } from '@/lib/api';

// Lazy-load Plotly
let PlotlyLoaded = null;
async function getPlotly() {
  if (PlotlyLoaded) return PlotlyLoaded;
  try {
    const mod = await import('react-plotly.js');
    PlotlyLoaded = mod.default;
    return PlotlyLoaded;
  } catch { return null; }
}

const EXAMPLE_QUESTIONS = [
  "Which channels have the biggest processed vs published gap?",
  "Show me the monthly upload and publish trend",
  "Which user has the highest publish rate?",
  "What input types are most common?",
  "Top 10 videos by published duration",
  "Which platforms are used most for publishing?",
];

// ─── Message part renderers ───────────────────────────────────────────────────

function SqlBlock({ sql }) {
  const [open, setOpen] = useState(false);
  if (!sql) return null;
  return (
    <div className="rounded-lg border border-border bg-muted/40 overflow-hidden text-xs">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex w-full items-center justify-between px-4 py-2 text-muted-foreground hover:text-foreground"
      >
        <span className="font-mono text-[11px] font-medium">SQL Generated</span>
        {open ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
      </button>
      {open && (
        <pre className="overflow-x-auto px-4 pb-3 font-mono text-[11px] text-foreground/80 whitespace-pre-wrap border-t border-border">
          {sql}
        </pre>
      )}
    </div>
  );
}

function DataTableBlock({ rows }) {
  const [show, setShow] = useState(false);
  if (!rows?.length) return null;
  const cols    = Object.keys(rows[0]);
  const preview = rows.slice(0, 15);

  return (
    <div className="rounded-lg border border-border bg-muted/40 overflow-hidden text-xs">
      <button
        onClick={() => setShow(o => !o)}
        className="flex w-full items-center justify-between px-4 py-2 text-muted-foreground hover:text-foreground"
      >
        <span className="flex items-center gap-2">
          <Table className="h-3.5 w-3.5" />
          <span className="font-medium">{rows.length} row{rows.length !== 1 ? 's' : ''}</span>
        </span>
        {show ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
      </button>
      {show && (
        <div className="overflow-x-auto border-t border-border">
          <table className="min-w-full text-[11px]">
            <thead className="bg-muted/60">
              <tr>
                {cols.map(c => (
                  <th key={c} className="px-3 py-2 text-left font-semibold text-muted-foreground whitespace-nowrap">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.map((row, i) => (
                <tr key={i} className="border-t border-border/50 hover:bg-muted/30">
                  {cols.map(c => (
                    <td key={c} className="px-3 py-1.5 text-foreground/80 whitespace-nowrap">
                      {String(row[c] ?? '')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length > 15 && (
            <p className="px-3 py-2 text-[11px] text-muted-foreground border-t border-border">
              + {rows.length - 15} more rows
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function PlotlyBlock({ chartJson, chartType }) {
  const [Plot, setPlot]   = useState(null);
  const [noLib, setNoLib] = useState(false);

  useEffect(() => {
    getPlotly().then(p => p ? setPlot(() => p) : setNoLib(true));
  }, []);

  if (noLib) {
    return (
      <div className="rounded-lg border border-border bg-muted/40 px-4 py-3 text-xs text-muted-foreground">
        <BarChart2 className="inline h-4 w-4 mr-2" />
        Chart available. Install:{' '}
        <code className="font-mono bg-muted px-1 rounded">npm install react-plotly.js plotly.js-dist-min</code>
      </div>
    );
  }
  if (!Plot || !chartJson) return null;

  const layout = {
    ...chartJson.layout,
    paper_bgcolor: 'transparent',
    plot_bgcolor:  'rgba(255,255,255,0.02)',
    font:          { color: '#cbd5e1', size: 11 },
    margin:        { l: 60, r: 20, t: 40, b: 60 },
    height:        360,
    autosize:      true,
    showlegend:    true,
    legend:        { bgcolor: 'rgba(0,0,0,0)', font: { color: '#94a3b8' } },
    xaxis:         { ...chartJson.layout?.xaxis, gridcolor: '#2a2a2a', tickfont: { size: 10 } },
    yaxis:         { ...chartJson.layout?.yaxis, gridcolor: '#2a2a2a', tickfont: { size: 10 } },
  };

  return (
    <div className="rounded-lg border border-border bg-muted/40 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-border">
        <BarChart2 className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-xs capitalize text-muted-foreground">{chartType} chart</span>
      </div>
      <Plot
        data={chartJson.data}
        layout={layout}
        config={{ displayModeBar: false, responsive: true }}
        style={{ width: '100%' }}
        useResizeHandler
      />
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function ChatbotPage() {
  const [input, setInput]       = useState('');
  const [streaming, setStreaming] = useState(false);
  const [messages, setMessages]  = useState([]);
  const bottomRef = useRef(null);
  const esRef     = useRef(null);
  const inputRef  = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const addPart = useCallback((msgId, part) => {
    setMessages(prev => prev.map(m =>
      m.id === msgId ? { ...m, parts: [...m.parts, part] } : m
    ));
  }, []);

  const removeThinking = useCallback((msgId) => {
    setMessages(prev => prev.map(m =>
      m.id === msgId ? { ...m, parts: m.parts.filter(p => p.type !== 'thinking') } : m
    ));
  }, []);

  const ask = useCallback((question) => {
    question = question.trim();
    if (!question || streaming) return;

    setInput('');
    setStreaming(true);

    const botId = `b-${Date.now()}`;

    setMessages(prev => [
      ...prev,
      { id: `u-${Date.now()}`, role: 'user',  content: question },
      { id: botId,             role: 'bot',   parts: [{ type: 'thinking' }] },
    ]);

    let thinkingDone = false;
    const clearThinking = () => {
      if (thinkingDone) return;
      thinkingDone = true;
      removeThinking(botId);
    };

    const url = `${BASE_URL}/api/chat/stream?question=${encodeURIComponent(question)}`;
    const es  = new EventSource(url);
    esRef.current = es;

    es.addEventListener('sql_ready',     e => { clearThinking(); addPart(botId, { type: 'sql',     ...JSON.parse(e.data) }); });
    es.addEventListener('data_ready',    e => { clearThinking(); addPart(botId, { type: 'table',   ...JSON.parse(e.data) }); });
    es.addEventListener('insight_ready', e => { clearThinking(); addPart(botId, { type: 'insight', ...JSON.parse(e.data) }); });
    es.addEventListener('chart_ready',   e => { clearThinking(); addPart(botId, { type: 'chart',   ...JSON.parse(e.data) }); });
    es.addEventListener('error',         e => { clearThinking(); addPart(botId, { type: 'error',   ...JSON.parse(e.data || '{}') }); });

    es.addEventListener('done', e => {
      clearThinking();
      const { took_ms } = JSON.parse(e.data || '{}');
      if (took_ms) addPart(botId, { type: 'meta', took_ms });
      es.close();
      setStreaming(false);
      inputRef.current?.focus();
    });

    es.onerror = () => {
      clearThinking();
      addPart(botId, { type: 'error', message: 'Connection error. Is the backend running?' });
      es.close();
      setStreaming(false);
    };
  }, [input, streaming, addPart, removeThinking]);

  useEffect(() => () => esRef.current?.close(), []);

  const clearChat = () => {
    esRef.current?.close();
    setMessages([]);
    setStreaming(false);
  };

  return (
    <DashboardLayout title="AI Analytics Chat">
      <div className="flex h-[calc(100vh-8rem)] flex-col gap-4">

        {/* Example questions (only when chat is empty) */}
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center flex-1 gap-6">
            <div className="flex items-center gap-3">
              <Sparkles className="h-8 w-8 text-primary" />
              <div>
                <h2 className="text-xl font-semibold">Analytics Assistant</h2>
                <p className="text-sm text-muted-foreground">Ask anything about your video data</p>
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 w-full max-w-3xl">
              {EXAMPLE_QUESTIONS.map(q => (
                <button
                  key={q}
                  onClick={() => ask(q)}
                  className="rounded-lg border border-border bg-card p-3 text-left text-sm text-muted-foreground hover:border-primary hover:text-foreground transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Chat messages */}
        {messages.length > 0 && (
          <ScrollArea className="flex-1 pr-2">
            <div className="flex flex-col gap-4 pb-4">
              {messages.map(msg => (
                <div key={msg.id}>
                  {msg.role === 'user' ? (
                    <div className="flex justify-end">
                      <div className="max-w-2xl rounded-2xl bg-primary px-4 py-2.5 text-sm text-primary-foreground">
                        {msg.content}
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-3 max-w-3xl">
                      {msg.parts?.map((part, i) => {
                        switch (part.type) {
                          case 'thinking': return (
                            <div key={i} className="flex items-center gap-2 text-sm text-muted-foreground">
                              <Loader2 className="h-4 w-4 animate-spin" />
                              Analysing your question…
                            </div>
                          );
                          case 'sql':    return <SqlBlock       key={i} sql={part.sql} />;
                          case 'table':  return <DataTableBlock key={i} rows={part.rows} />;
                          case 'insight':return (
                            <div key={i} className="rounded-lg border border-border bg-card px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap">
                              {part.insight}
                            </div>
                          );
                          case 'chart':  return <PlotlyBlock    key={i} chartJson={part.chart_json} chartType={part.chart_type} />;
                          case 'error':  return (
                            <div key={i} className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                              {part.message || 'An error occurred.'}
                            </div>
                          );
                          case 'meta': return (
                            <p key={i} className="text-[11px] text-muted-foreground">
                              Completed in {(part.took_ms / 1000).toFixed(1)}s
                            </p>
                          );
                          default: return null;
                        }
                      })}
                    </div>
                  )}
                </div>
              ))}
              <div ref={bottomRef} />
            </div>
          </ScrollArea>
        )}

        {/* Input bar */}
        <div className="flex items-center gap-2 border-t border-border pt-3">
          {messages.length > 0 && (
            <Button variant="ghost" size="icon" onClick={clearChat} title="Clear chat" className="shrink-0">
              <RotateCcw className="h-4 w-4" />
            </Button>
          )}
          <Input
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && ask(input)}
            placeholder="Ask about your video data…"
            className="flex-1"
            disabled={streaming}
          />
          <Button onClick={() => ask(input)} disabled={streaming || !input.trim()} className="shrink-0">
            {streaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            <span className="ml-2 hidden sm:inline">Ask</span>
          </Button>
        </div>
      </div>
    </DashboardLayout>
  );
}
