import { useFilters } from '@/contexts/FilterContext';
import { clients, channels, users, dimensions } from '@/data/mockData';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { X } from 'lucide-react';

export function GlobalFilterPanel() {
  const { filters, setFilters } = useFilters();

  const toggleFilter = (key, value) => {
    setFilters(prev => {
      const arr = prev[key];
      return {
        ...prev,
        [key]: arr.includes(value) ? arr.filter(v => v !== value) : [...arr, value],
      };
    });
  };

  const clearAll = () => {
    setFilters(prev => ({
      ...prev,
      client: [], channel: [], user: [], language: [],
      inputType: [], outputType: [], publishedStatus: [],
      platform: [], team: [],
    }));
  };

  const activeCount = [
    filters.client, filters.channel, filters.user, filters.language,
    filters.inputType, filters.outputType, filters.publishedStatus,
    filters.platform, filters.team,
  ].reduce((s, a) => s + a.length, 0);

  return (
    <div className="flex items-center gap-2 overflow-x-auto border-y border-border bg-background p-2 no-scrollbar">
        <FilterSelect label="Client" options={clients.map(c => ({ value: c.id, label: c.name }))}
          selected={filters.client} onToggle={(v) => toggleFilter('client', v)} />
        <FilterSelect label="Channel" options={channels.map(c => ({ value: c.id, label: c.name }))}
          selected={filters.channel} onToggle={(v) => toggleFilter('channel', v)} />
        <FilterSelect label="Language" options={dimensions.languages.map(l => ({ value: l, label: l }))}
          selected={filters.language} onToggle={(v) => toggleFilter('language', v)} />
        <FilterSelect label="Input Type" options={dimensions.inputTypes.map(t => ({ value: t, label: t }))}
          selected={filters.inputType} onToggle={(v) => toggleFilter('inputType', v)} />
        <FilterSelect label="Output Type" options={dimensions.outputTypes.map(t => ({ value: t, label: t }))}
          selected={filters.outputType} onToggle={(v) => toggleFilter('outputType', v)} />
        <FilterSelect label="Platform" options={dimensions.platforms.map(p => ({ value: p, label: p }))}
          selected={filters.platform} onToggle={(v) => toggleFilter('platform', v)} />
        <FilterSelect label="Team" options={dimensions.teams.map(t => ({ value: t, label: t }))}
          selected={filters.team} onToggle={(v) => toggleFilter('team', v)} />
        <FilterSelect label="Status" options={[{ value: 'Published', label: 'Published' }, { value: 'Unpublished', label: 'Unpublished' }]}
          selected={filters.publishedStatus} onToggle={(v) => toggleFilter('publishedStatus', v)} />
      
      {activeCount > 0 && (
        <Button variant="ghost" size="sm" onClick={clearAll} className="h-8 px-2 text-xs text-muted-foreground hover:text-foreground shrink-0">
          Clear all
          <X className="ml-1.5 h-3 w-3" />
        </Button>
      )}
    </div>
  );
}

function FilterSelect({ label, options, selected, onToggle }) {
  return (
    <Select onValueChange={onToggle}>
      <SelectTrigger className="h-8 w-auto min-w-[100px] text-xs shrink-0 border-none shadow-none focus:ring-0 focus:ring-offset-0 bg-[#1C1D1F]">
        <SelectValue placeholder={selected.length ? `${selected.length} selected` : label} />
        </SelectTrigger>
        <SelectContent>
          {options.map(opt => (
            <SelectItem key={opt.value} value={opt.value}>
              <span className="flex items-center gap-2">
                {selected.includes(opt.value) && <span className="text-accent">✓</span>}
                {opt.label}
              </span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
  );
}
