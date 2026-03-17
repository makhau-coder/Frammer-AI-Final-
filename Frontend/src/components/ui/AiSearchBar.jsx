// src/components/ui/AiSearchBar.jsx
// FIX: Component now accepts and forwards all props (value, onChange, placeholder, disabled)

import { Search } from 'lucide-react';
import { Input } from './input';

export function AiSearchBar({ value, onChange, placeholder, disabled, onKeyDown }) {
  return (
    <div className="relative">
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
      <Input
        value={value}
        onChange={onChange}
        onKeyDown={onKeyDown}
        placeholder={placeholder || "Search videos…"}
        disabled={disabled}
        className="pl-9 h-11 text-base"
      />
    </div>
  );
}
