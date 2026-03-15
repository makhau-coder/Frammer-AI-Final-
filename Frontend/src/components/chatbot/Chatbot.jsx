import { useState, useRef } from 'react';
import { MessageCircle, X, Send } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { getPublishRate, getProcessedCount, getPublishedCount } from '@/services/dataProcessing';
import { clients, channels, users, videos as allVideos } from '@/data/mockData';

function getMockResponse(query, videos) {
  const q = query.toLowerCase();

  if (q.includes('publish rate') || q.includes('publish conversion')) {
    const byChannel = channels.map(ch => {
      const chVids = videos.filter(v => v.channel_id === ch.id);
      return { name: ch.name, rate: getPublishRate(chVids) * 100 };
    }).sort((a, b) => a.rate - b.rate);
    return `📊 **Publish Rates by Channel (lowest first):**\n${byChannel.slice(0, 5).map((c, i) => `${i + 1}. ${c.name}: ${c.rate.toFixed(1)}%`).join('\n')}`;
  }
  if (q.includes('longest video') || q.includes('longest')) {
    const sorted = [...videos].sort((a, b) => b.duration - a.duration).slice(0, 10);
    return `📹 **Top 10 Longest Videos:**\n${sorted.map((v, i) => `${i + 1}. ${v.headline} — ${(v.duration / 60).toFixed(0)}min`).join('\n')}`;
  }
  if (q.includes('language')) {
    const langs = {};
    videos.forEach(v => { langs[v.language] = (langs[v.language] || 0) + v.duration; });
    return `🌍 **Usage Hours by Language:**\n${Object.entries(langs).sort(([, a], [, b]) => b - a).map(([l, d]) => `- ${l}: ${(d / 3600).toFixed(1)}h`).join('\n')}`;
  }
  if (q.includes('client') || q.includes('top client')) {
    const byClient = clients.map(c => ({
      name: c.name,
      count: videos.filter(v => v.client_id === c.id).length,
    })).sort((a, b) => b.count - a.count);
    return `🏢 **Videos by Client:**\n${byClient.map((c, i) => `${i + 1}. ${c.name}: ${c.count} videos`).join('\n')}`;
  }
  if (q.includes('gap') || q.includes('drop')) {
    const byChannel = channels.map(ch => {
      const chVids = videos.filter(v => v.channel_id === ch.id);
      return { name: ch.name, gap: getProcessedCount(chVids) - getPublishedCount(chVids) };
    }).sort((a, b) => b.gap - a.gap);
    return `⚠️ **Biggest Processed→Published Gaps:**\n${byChannel.slice(0, 5).map((c, i) => `${i + 1}. ${c.name}: ${c.gap} videos unpublished`).join('\n')}`;
  }
  return `I can help with queries like:\n- "Which channels have lowest publish rate?"\n- "Top 10 longest videos"\n- "Usage hours by language"\n- "Top clients by video count"\n- "Channels with biggest processed vs published gap"`;
}

export function Chatbot() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([
    { role: 'bot', content: 'Hi! Ask me about your video analytics. Try "Which channels have lowest publish rate?"' },
  ]);
  const [input, setInput] = useState('');
  const scrollRef = useRef(null);

  const send = () => {
    if (!input.trim()) return;
    const userMsg = { role: 'user', content: input };
    const botMsg = { role: 'bot', content: getMockResponse(input, allVideos) };
    setMessages(prev => [...prev, userMsg, botMsg]);
    setInput('');
  };

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
    <div className="fixed bottom-6 right-6 z-50 flex w-80 flex-col rounded-lg border border-border bg-card shadow-2xl" style={{ height: 420 }}>
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <span className="text-sm font-semibold text-foreground">Analytics Assistant</span>
        <button onClick={() => setOpen(false)} className="text-muted-foreground hover:text-foreground">
          <X className="h-4 w-4" />
        </button>
      </div>
      <ScrollArea className="flex-1 p-3" ref={scrollRef}>
        <div className="flex flex-col gap-3">
          {messages.map((m, i) => (
            <div key={i} className={`text-xs leading-relaxed whitespace-pre-wrap rounded-lg px-3 py-2 ${
              m.role === 'user'
                ? 'ml-auto bg-primary text-primary-foreground max-w-[85%]'
                : 'mr-auto bg-secondary text-secondary-foreground max-w-[90%]'
            }`}>
              {m.content}
            </div>
          ))}
        </div>
      </ScrollArea>
      <div className="flex items-center gap-2 border-t border-border p-3">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder="Ask a question..."
          className="h-8 text-xs"
        />
        <Button size="icon" className="h-8 w-8 shrink-0" onClick={send}>
          <Send className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}
