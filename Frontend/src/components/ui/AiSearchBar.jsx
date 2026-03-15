import { Search } from 'lucide-react';
import { Input } from './input';

export function AiSearchBar() {
  return (
    <div className="relative">
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
      <Input
        placeholder="Ask AI to find videos, generate insights, or suggest content..."
        className="pl-9 h-11 text-base"
      />
    </div>
  );
}