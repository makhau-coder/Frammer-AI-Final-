/**
 * src/components/filters/GlobalFilterPanel.jsx
 *
 * REWRITE: Removed mockData dependency entirely.
 * Dimension options are fetched from the real backend:
 *   /api/input-types, /api/languages, /api/output-types,
 *   /api/publishing-platforms
 *
 * Requires FilterProvider to be in the component tree.
 * Currently not mounted in DashboardLayout — add it there
 * under Header if you want it on every page.
 */

import { useFilters } from '@/contexts/FilterContext';
import { useQuery } from '@tanstack/react-query';
import { api, extractArray } from '@/lib/api';
import {
  Select, SelectContent, SelectItem,
  SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { X } from 'lucide-react';

export function GlobalFilterPanel() {
  const { filters, updateFilter, clearFilters, activeCount } = useFilters();

  /* ── Fetch dimension options from real API ─────────────────────── */

  const { data: inputTypesRaw = [] } = useQuery({
    queryKey: ['inputTypes'],
    queryFn:  api.inputTypes,
    staleTime: Infinity,
  });
  const { data: languagesRaw = [] } = useQuery({
    queryKey: ['languages'],
    queryFn:  api.languages,
    staleTime: Infinity,
  });
  const { data: outputTypesRaw = [] } = useQuery({
    queryKey: ['outputTypes'],
    queryFn:  api.outputTypes,
    staleTime: Infinity,
  });
  const { data: platformsRaw = [] } = useQuery({
    queryKey: ['platforms'],
    queryFn:  api.platforms,
    staleTime: Infinity,
  });

  const inputTypes  = extractArray(inputTypesRaw).map(t => t.input_type);
  const languages   = extractArray(languagesRaw).map(l => l.language);
  const outputTypes = extractArray(outputTypesRaw).map(o => o.output_type);

  // Platform options — deduplicate from channel×platform data
  const platforms = [...new Set(
    extractArray(platformsRaw).map(p => p.platform).filter(Boolean)
  )];

  const statusOptions = [
    { value: 'published',     label: 'Published' },
    { value: 'not_published', label: 'Not Published' },
  ];

  return (
    <div className="flex items-center gap-2 overflow-x-auto border-b border-border bg-background p-2 no-scrollbar">

      <FilterSelect
        label="Input Type"
        options={inputTypes.map(t => ({ value: t, label: t }))}
        value={filters.inputType}
        onChange={v => updateFilter('inputType', v === 'all' ? '' : v)}
      />

      <FilterSelect
        label="Language"
        options={languages.map(l => ({ value: l, label: l }))}
        value={filters.language}
        onChange={v => updateFilter('language', v === 'all' ? '' : v)}
      />

      <FilterSelect
        label="Output Type"
        options={outputTypes.map(t => ({ value: t, label: t }))}
        value={filters.outputType}
        onChange={v => updateFilter('outputType', v === 'all' ? '' : v)}
      />

      <FilterSelect
        label="Platform"
        options={platforms.map(p => ({ value: p, label: p }))}
        value={filters.platform}
        onChange={v => updateFilter('platform', v === 'all' ? '' : v)}
      />

      <FilterSelect
        label="Status"
        options={statusOptions}
        value={filters.publishedStatus}
        onChange={v => updateFilter('publishedStatus', v === 'all' ? '' : v)}
      />

      {activeCount > 0 && (
        <Button
          variant="ghost" size="sm"
          onClick={clearFilters}
          className="h-8 px-2 text-xs text-muted-foreground hover:text-foreground shrink-0"
        >
          Clear all ({activeCount})
          <X className="ml-1.5 h-3 w-3" />
        </Button>
      )}
    </div>
  );
}

function FilterSelect({ label, options, value, onChange }) {
  return (
    <Select value={value || 'all'} onValueChange={onChange}>
      <SelectTrigger className="h-8 w-auto min-w-[110px] text-xs shrink-0 border-none shadow-none bg-[#1C1D1F]">
        <SelectValue placeholder={label} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="all">{label} (all)</SelectItem>
        {options.map(opt => (
          <SelectItem key={opt.value} value={opt.value}>
            {opt.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
