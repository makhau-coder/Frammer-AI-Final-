/**
 * src/pages/ChatbotPage.jsx
 *
 * AI Analytics Chat — Frammer NLP interface
 * POST /api/chat  →  insight · Plotly chart · data table · SQL
 *
 * Handles all agent response states:
 *   success=true       → insight + optional chart + data table + SQL
 *   needs_input=true   → agent asking a clarification question (amber)
 *   cannot_answer=true → out-of-scope with suggestions (yellow)
 *   error              → pipeline error (red)
 */

import { useState, useRef, useEffect, useCallback } from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";
import {
  Send, Loader2, User, AlertTriangle, XCircle,
  ChevronDown, ChevronUp, Database, Sparkles, Copy,
  Check, BarChart2, Table2, Code2, Lightbulb,
  HelpCircle, ArrowRight, MessageSquarePlus,
} from "lucide-react";

import { BASE_URL } from "@/lib/api";
const API = BASE_URL || "http://localhost:8000";

const STARTERS = [
  { icon: "📈", text: "Show me the monthly upload trend" },
  { icon: "🏆", text: "Which user uploaded the most videos?" },
  { icon: "📊", text: "What is the publish rate for each channel?" },
  { icon: "⏱️", text: "How many hours has each user uploaded?" },
  { icon: "🌍", text: "Which language has the best publish rate?" },
  { icon: "🔝", text: "Top users by creation multiplier" },
  { icon: "📅", text: "Which month had the highest creation multiplier?" },
  { icon: "🎯", text: "Channel-wise publishing platform breakdown" },
];

export default function ChatbotPage() {
  const [messages,   setMessages]  = useState([]);
  const [input,      setInput]     = useState("");
  const [loading,    setLoading]   = useState(false);
  const [sessionId,  setSessionId] = useState(() => crypto.randomUUID());
  const bottomRef  = useRef(null);
  const inputRef   = useRef(null);

  // Start a completely fresh conversation with a new session ID
  const newChat = () => {
    if (loading) return;
    setMessages([]);
    setInput("");
    setSessionId(crypto.randomUUID());
    setTimeout(() => inputRef.current?.focus(), 50);
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Auto-grow textarea height
  const growTA = useCallback((el) => {
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }, []);

  const send = useCallback(async (question) => {
  const q = (question ?? input).trim();
  if (!q || loading) return;

  setInput("");
  setLoading(true);
  setMessages(prev => [...prev, { role: "user", text: q }]);

  try {
    const res = await fetch(`${API}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q, session_id: sessionId }),
    });

    const data = await res.json(); // ✅ only once

    if (!res.ok) {
      throw new Error(data.detail || `HTTP ${res.status}`);
    }

    setMessages(prev => [...prev, { role: "ai", data }]);

  } catch (e) {
    setMessages(prev => [...prev, {
      role: "ai",
      data: {
        success: false,
        error: String(e.message || e),
      }
    }]);
  } finally {
    setLoading(false);
    setTimeout(() => inputRef.current?.focus(), 50);
  }
}, [input, loading, sessionId]);

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  };

  return (
    <DashboardLayout title="AI Analytics Chat">
      <div className="flex flex-col h-[calc(100vh-7rem)]">

        {/* ── Toolbar ───────────────────────────────────────────────── */}
        {messages.length > 0 && (
          <div className="flex justify-end mb-3 shrink-0">
            <button
              onClick={newChat}
              disabled={loading}
              title="Start a new conversation"
              className="flex items-center gap-2 rounded-xl border border-border/60 bg-card/60 px-4 py-2 text-xs text-muted-foreground hover:text-foreground hover:border-primary/40 hover:bg-primary/5 transition-all disabled:opacity-40"
            >
              <MessageSquarePlus className="h-3.5 w-3.5" />
              New Chat
            </button>
          </div>
        )}

        {/* ── Feed ──────────────────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto space-y-5 pb-4 pr-1">

          {/* Welcome */}
          {messages.length === 0 && (
            <motion.div
              initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
              className="flex flex-col items-center justify-center min-h-[60vh] gap-7 text-center"
            >
              <div className="relative">
                <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-indigo-500/20 to-violet-500/20 border border-indigo-500/30 flex items-center justify-center shadow-lg">
                  <Sparkles className="h-7 w-7 text-indigo-400" />
                </div>
                <span className="absolute -bottom-1 -right-1 h-4 w-4 rounded-full bg-green-500 border-2 border-background" />
              </div>

              <div className="space-y-2 max-w-md">
                <h2 className="text-xl font-semibold">Ask anything about your data</h2>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  Natural language → SQL → insights + charts.
                  Powered by Gemini 2.5 Flash and your Frammer DuckDB.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-xl">
                {STARTERS.map((s, i) => (
                  <motion.button key={i}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.08 + i * 0.04 }}
                    onClick={() => send(s.text)}
                    className="group flex items-center gap-3 text-left rounded-xl border border-border/60 bg-card/60 px-4 py-3 text-xs text-muted-foreground hover:text-foreground hover:border-primary/40 hover:bg-primary/5 transition-all"
                  >
                    <span className="text-base shrink-0">{s.icon}</span>
                    <span className="flex-1 leading-snug">{s.text}</span>
                    <ArrowRight className="h-3 w-3 shrink-0 opacity-0 group-hover:opacity-50 transition-opacity" />
                  </motion.button>
                ))}
              </div>
            </motion.div>
          )}

          {/* Messages */}
          {messages.map((msg, i) => (
            <motion.div key={i}
              initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
            >
              {msg.role === "user"
                ? <UserBubble text={msg.text} />
                : <AIBubble   data={msg.data} />}
            </motion.div>
          ))}

          {/* Typing */}
          {loading && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="flex items-start gap-3">
              <AIAvatar pulse />
              <div className="flex items-center gap-2 rounded-2xl rounded-tl-sm border border-border bg-card px-5 py-3.5">
                {[0, 150, 300].map(d => (
                  <div key={d} className="h-1.5 w-1.5 rounded-full bg-indigo-400/60 animate-bounce"
                    style={{ animationDelay: `${d}ms` }} />
                ))}
                <span className="text-xs text-muted-foreground ml-1">Thinking…</span>
              </div>
            </motion.div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* ── Input ─────────────────────────────────────────────────── */}
        <div className="mt-3">
          <div className="flex items-end gap-2 rounded-2xl border border-border bg-card p-3 shadow-sm focus-within:border-indigo-500/40 transition-colors">
            <textarea
              ref={el => { inputRef.current = el; }}
              value={input}
              rows={1}
              onChange={e => { setInput(e.target.value); growTA(e.target); }}
              onKeyDown={handleKey}
              placeholder="Ask about uploads, channels, users, durations, publish rates…"
              style={{ resize: "none", overflow: "hidden", minHeight: 24 }}
              className="flex-1 bg-transparent text-sm placeholder:text-muted-foreground/40 outline-none leading-relaxed"
            />
            <button onClick={() => send()} disabled={!input.trim() || loading}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground disabled:opacity-25 hover:opacity-85 transition-opacity">
              {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
            </button>
          </div>
          <p className="mt-1.5 text-center text-[10px] text-muted-foreground/30">
            Enter to send · Shift+Enter for new line
          </p>
        </div>

      </div>
    </DashboardLayout>
  );
}

// ─── User bubble ──────────────────────────────────────────────────────
function UserBubble({ text }) {
  return (
    <div className="flex items-end gap-2.5 justify-end">
      <div className="max-w-[75%] rounded-2xl rounded-br-sm bg-primary px-4 py-2.5 text-sm text-primary-foreground shadow-sm">
        {text}
      </div>
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-muted border border-border">
        <User className="h-3.5 w-3.5 text-muted-foreground" />
      </div>
    </div>
  );
}

// ─── AI Avatar ───────────────────────────────────────────────────────
function AIAvatar({ pulse = false }) {
  return (
    <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full
      bg-gradient-to-br from-indigo-500/20 to-violet-500/20 border border-indigo-500/30
      ${pulse ? "animate-pulse" : ""}`}>
      <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
    </div>
  );
}

// ─── AI bubble — all states ───────────────────────────────────────────
function AIBubble({ data }) {
  const [showTable, setShowTable] = useState(false);
  const [showSQL,   setShowSQL]   = useState(false);
  const [copied,    setCopied]    = useState(false);

  const isError      = !data.success && !data.needs_input && !data.cannot_answer;
  const isClarify    = data.needs_input;
  const isOutOfScope = data.cannot_answer;

  function copySQL() {
    navigator.clipboard.writeText(data.sql).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="flex items-start gap-3">
      <AIAvatar />
      <div className="flex-1 min-w-0 space-y-2">

        {/* Error */}
        {isError && (
          <div className="rounded-2xl rounded-tl-sm border border-border bg-muted/20 px-4 py-3.5">
            <div className="flex items-center gap-2 mb-1.5">
              <XCircle className="h-3.5 w-3.5 text-red-400" />
              <span className="text-[10px] font-bold uppercase tracking-widest text-red-400">Pipeline Error</span>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">{data.error}</p>
          </div>
        )}

        {/* Clarification */}
        {isClarify && (
          <div className="rounded-2xl rounded-tl-sm border border-border bg-muted/20 px-4 py-3.5">
            <div className="flex items-center gap-2 mb-1.5">
              <HelpCircle className="h-3.5 w-3.5 text-amber-400" />
              <span className="text-[10px] font-bold uppercase tracking-widest text-amber-400">Clarification needed</span>
            </div>
            <div className="prose prose-sm prose-invert max-w-none prose-p:text-muted-foreground prose-p:leading-relaxed prose-p:my-0 prose-strong:text-foreground">
              <ReactMarkdown>{data.message}</ReactMarkdown>
            </div>
          </div>
        )}

        {/* Cannot answer */}
        {isOutOfScope && (
          <div className="rounded-2xl rounded-tl-sm border border-border bg-muted/20 px-4 py-3.5">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="h-3.5 w-3.5 text-yellow-500" />
              <span className="text-[10px] font-bold uppercase tracking-widest text-yellow-500">Out of scope</span>
            </div>
            <CannotAnswerBody message={data.message} />
          </div>
        )}

        {/* Success */}
        {data.success && (
          <div className="rounded-2xl rounded-tl-sm border border-border bg-card overflow-hidden">

            {/* Insight */}
            {data.insight && (
              <div className="px-4 pt-4 pb-3">
                <div className="flex items-center gap-1.5 mb-2.5">
                  <Lightbulb className="h-3.5 w-3.5 text-indigo-400" />
                  <span className="text-[10px] font-bold uppercase tracking-widest text-indigo-400">Insight</span>
                </div>
                <div className="prose prose-sm prose-invert max-w-none
                  prose-p:text-foreground/90 prose-p:leading-relaxed prose-p:my-1.5
                  prose-strong:text-foreground prose-strong:font-semibold
                  prose-ul:my-1.5 prose-ul:pl-4 prose-li:my-0.5 prose-li:text-foreground/85
                  prose-ol:my-1.5 prose-ol:pl-4
                  prose-headings:text-foreground prose-headings:font-semibold
                  prose-h3:text-sm prose-h3:mt-3 prose-h3:mb-1
                  prose-code:text-indigo-300 prose-code:bg-muted/40 prose-code:px-1 prose-code:rounded prose-code:text-xs
                  prose-blockquote:border-indigo-500/40 prose-blockquote:text-muted-foreground">
                  <ReactMarkdown>{data.insight}</ReactMarkdown>
                </div>
              </div>
            )}

            {/* Chart */}
            {data.chart_url && (
              <div className="px-4 pb-3">
                <div className="flex items-center gap-1.5 mb-2">
                  <BarChart2 className="h-3.5 w-3.5 text-emerald-400" />
                  <span className="text-[10px] font-bold uppercase tracking-widest text-emerald-400 capitalize">
                    {data.chart_type || "chart"}
                  </span>
                </div>
                <div className="rounded-xl overflow-hidden border border-border/40 bg-[#0f1117]">
                  <img
                    src={`${API}${data.chart_url}`}
                    alt={`${data.chart_type} chart`}
                    className="w-full object-contain"
                    style={{ maxHeight: 420 }}
                    onError={e => { e.currentTarget.closest(".rounded-xl").style.display = "none"; }}
                  />
                </div>
              </div>
            )}

            {/* Meta row */}
            <div className="px-4 pb-2.5 flex flex-wrap gap-3 text-[11px] text-muted-foreground/50">
              {data.row_count > 0 && (
                <span className="flex items-center gap-1">
                  <Database className="h-3 w-3" />
                  {data.row_count.toLocaleString()} row{data.row_count !== 1 ? "s" : ""}
                </span>
              )}
              {data.retrieved_tables?.length > 0 && (
                <span className="truncate max-w-xs font-mono">
                  {data.retrieved_tables.slice(0, 2).join(", ")}
                  {data.retrieved_tables.length > 2 && ` +${data.retrieved_tables.length - 2}`}
                </span>
              )}
            </div>

            {/* Data table */}
            {data.data?.length > 0 && (
              <div className="border-t border-border/40">
                <button onClick={() => setShowTable(v => !v)}
                  className="w-full flex items-center justify-between px-4 py-2.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/20 transition-colors">
                  <span className="flex items-center gap-2">
                    <Table2 className="h-3.5 w-3.5" />
                    Data
                    <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-mono">
                      {data.row_count}
                    </span>
                  </span>
                  {showTable ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                </button>
                <AnimatePresence>
                  {showTable && (
                    <motion.div
                      initial={{ height: 0 }} animate={{ height: "auto" }} exit={{ height: 0 }}
                      transition={{ duration: 0.15 }} className="overflow-hidden">
                      <DataTable rows={data.data} />
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )}

            {/* SQL */}
            {data.sql && (
              <div className="border-t border-border/40">
                <button onClick={() => setShowSQL(v => !v)}
                  className="w-full flex items-center justify-between px-4 py-2.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/20 transition-colors">
                  <span className="flex items-center gap-2">
                    <Code2 className="h-3.5 w-3.5" />
                    SQL
                  </span>
                  {showSQL ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                </button>
                <AnimatePresence>
                  {showSQL && (
                    <motion.div
                      initial={{ height: 0 }} animate={{ height: "auto" }} exit={{ height: 0 }}
                      transition={{ duration: 0.15 }} className="overflow-hidden">
                      <div className="relative border-t border-border/40 bg-muted/20">
                        <button onClick={copySQL} title="Copy SQL"
                          className="absolute right-3 top-2.5 rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
                          {copied
                            ? <Check className="h-3.5 w-3.5 text-green-400" />
                            : <Copy  className="h-3.5 w-3.5" />}
                        </button>
                        <pre className="px-4 py-3.5 pr-10 text-[11px] text-muted-foreground overflow-x-auto whitespace-pre leading-relaxed font-mono">
                          {data.sql}
                        </pre>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )}

          </div>
        )}
      </div>
    </div>
  );
}

// ─── Cannot-answer message with suggestion list ───────────────────────
function CannotAnswerBody({ message }) {
  if (!message) return null;
  const parts       = message.split("|").map(p => p.trim()).filter(Boolean);
  const reason      = parts[0];
  const suggestions = parts.slice(1);
  return (
    <div className="space-y-3">
      <div className="prose prose-sm prose-invert max-w-none prose-p:text-muted-foreground prose-p:leading-relaxed prose-p:my-0 prose-strong:text-foreground">
        <ReactMarkdown>{reason}</ReactMarkdown>
      </div>
      {suggestions.length > 0 && (
        <div>
          <p className="text-[11px] text-muted-foreground/50 mb-1.5">You could try:</p>
          <div className="space-y-1">
            {suggestions.map((s, i) => (
              <div key={i} className="flex items-start gap-2 text-xs text-muted-foreground">
                <span className="text-muted-foreground/50 shrink-0 font-mono">{i + 1}.</span>
                <span>{s}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Data table ───────────────────────────────────────────────────────
function DataTable({ rows }) {
  if (!rows?.length) return null;
  const cols    = Object.keys(rows[0]);
  const display = rows.slice(0, 100);

  const isNum = col => rows.slice(0, 5).every(r => r[col] === null || typeof r[col] === "number");

  function fmt(v) {
    if (v === null || v === undefined) return <span className="text-muted-foreground/25">—</span>;
    if (typeof v === "boolean")
      return <span className={v ? "text-green-400" : "text-muted-foreground/40"}>{v ? "Yes" : "No"}</span>;
    if (typeof v === "number") return v.toLocaleString();
    return String(v);
  }

  return (
    <div className="overflow-auto max-h-72 border-t border-border/30">
      <table className="min-w-full text-xs">
        <thead className="sticky top-0 z-10 bg-muted/60 backdrop-blur-sm">
          <tr>
            {cols.map(col => (
              <th key={col}
                className={`px-3.5 py-2 font-semibold text-muted-foreground whitespace-nowrap border-b border-border/30
                  ${isNum(col) ? "text-right" : "text-left"}`}>
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {display.map((row, i) => (
            <tr key={i}
              className={`border-b border-border/20 hover:bg-primary/5 transition-colors
                ${i % 2 !== 0 ? "bg-muted/10" : ""}`}>
              {cols.map(col => (
                <td key={col}
                  className={`px-3.5 py-2 whitespace-nowrap font-mono
                    ${isNum(col) ? "text-right" : "text-left"}`}>
                  {fmt(row[col])}
                </td>
              ))}
            </tr>
          ))}
          {rows.length > 100 && (
            <tr>
              <td colSpan={cols.length} className="px-3.5 py-2.5 text-center text-muted-foreground/40 text-[11px] italic">
                Showing 100 of {rows.length.toLocaleString()} rows
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}