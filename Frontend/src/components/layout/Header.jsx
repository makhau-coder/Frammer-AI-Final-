import { SidebarTrigger } from '@/components/ui/sidebar';
import { Bell, TrendingUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useState, useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';

function KpiTicker() {
  const { data: monthlyData = [] } = useQuery({
    queryKey: ['monthlyData'],
    queryFn: async () => {
      const res = await fetch("http://localhost:8000/api/monthly");
      if (!res.ok) return [];
      const data = await res.json();
      return Array.isArray(data) ? data.filter(month => (month.uploaded_count || 0) > 0 || (month.created_count || 0) > 0 || (month.published_count || 0) > 0) : [];
    }
  });

  const [currentIndex, setCurrentIndex] = useState(0);

  const messages = useMemo(() => {
    if (!Array.isArray(monthlyData) || monthlyData.length < 2) return ["Gathering performance metrics..."];
    const curr = monthlyData[monthlyData.length - 1] || {};
    const prev = monthlyData[monthlyData.length - 2] || {};
    
    const calc = (c, p) => (p || 0) > 0 ? (((c || 0) - p) / p) * 100 : 0;
    
    const uploadGrowth = calc(curr.uploaded_count, prev.uploaded_count);
    const processGrowth = calc(curr.created_count, prev.created_count);
    const publishGrowth = calc(curr.published_count, prev.published_count);

    const msgs = [];
    if (uploadGrowth !== 0 && !Number.isNaN(uploadGrowth)) msgs.push(`Number of uploaded videos ${uploadGrowth >= 0 ? 'increased' : 'decreased'} by ${Math.abs(uploadGrowth).toFixed(1)}% vs last month`);
    if (processGrowth !== 0 && !Number.isNaN(processGrowth)) msgs.push(`Processed videos ${processGrowth >= 0 ? 'increased' : 'decreased'} by ${Math.abs(processGrowth).toFixed(1)}% vs last month`);
    if (publishGrowth !== 0 && !Number.isNaN(publishGrowth)) msgs.push(`Published videos ${publishGrowth >= 0 ? 'increased' : 'decreased'} by ${Math.abs(publishGrowth).toFixed(1)}% vs last month`);
    
    return msgs.length > 0 ? msgs : ["All metrics stable compared to last month"];
  }, [monthlyData]);

  useEffect(() => {
    if (messages.length <= 1) return;
    const timer = setInterval(() => {
      setCurrentIndex((prev) => (prev + 1) % messages.length);
    }, 5000);
    return () => clearInterval(timer);
  }, [messages.length]);

  return (
    <div className="hidden min-[1150px]:flex items-center justify-end overflow-hidden px-4 text-sm font-medium text-muted-foreground pointer-events-none text-right">
      <AnimatePresence mode="wait">
        <motion.div
          key={currentIndex}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.5 }}
          className="flex items-center gap-2"
        >
          <TrendingUp className="h-4 w-4 text-primary" />
          {messages[currentIndex]}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

export function Header({ title }) {
  return (
    <header className="sticky top-0 z-10 bg-background border-b border-border">
      <div className="flex h-14 items-center gap-4 px-4">
        <SidebarTrigger className="text-muted-foreground hover:text-foreground shrink-0" />
        <h1 className="text-lg font-semibold text-foreground truncate">{title}</h1>

        <div className="ml-auto flex items-center gap-3 shrink-0">
          <KpiTicker />
          <Button variant="ghost" size="icon" className="relative text-muted-foreground">
            <Bell className="h-4 w-4" />
            <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-primary" />
          </Button>
          <Avatar className="h-8 w-8 cursor-pointer">
            <AvatarFallback className="bg-primary text-primary-foreground text-xs font-medium">JD</AvatarFallback>
          </Avatar>
        </div>
      </div>
    </header>
  );
}
