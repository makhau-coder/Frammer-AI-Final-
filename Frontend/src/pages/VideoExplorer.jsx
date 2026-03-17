import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { AiSearchBar } from '@/components/ui/AiSearchBar';
import { StatusBadge } from '@/components/ui/StatusBadge';
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from '@/components/ui/table';
import {
  Select, SelectContent, SelectItem,
  SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Download, ChevronLeft, ChevronRight, X } from 'lucide-react';
import { api } from '@/lib/api';

// Fetch input types for the filter dropdown
function useInputTypes() {
  return useQuery({
    queryKey: ['inputTypes'],
    queryFn:  api.inputTypes,
    staleTime: Infinity,
  });
}

export default function VideoExplorer() {
  const [page, setPage]           = useState(1);
  const PAGE_SIZE                 = 50;
  const [search, setSearch]       = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [inputTypeFilter, setInputTypeFilter] = useState('');
  const [statusFilter, setStatusFilter]       = useState('');
  const [isExporting, setIsExporting] = useState(false);

  const { data: inputTypesRaw = [] } = useInputTypes();
  const inputTypes = Array.isArray(inputTypesRaw) ? inputTypesRaw : [];

  // Build query params
  const queryParams = {
    page,
    page_size: PAGE_SIZE,
    ...(search         && { search }),
    ...(inputTypeFilter && { input_type: inputTypeFilter }),
    ...(statusFilter    && { is_published: statusFilter === 'published' }),
  };

  const { data, isLoading } = useQuery({
    queryKey: ['videos', page, PAGE_SIZE, search, inputTypeFilter, statusFilter],
    queryFn:  () => api.videos(queryParams),
    keepPreviousData: true,
  });

  const videos     = Array.isArray(data?.data) ? data.data : [];
  const totalPages = data?.pages || 1;
  const total      = data?.total || 0;

  // FIX: Search now triggers API call instead of being disabled
  const applySearch = () => {
    setSearch(searchInput);
    setPage(1);
  };

  const clearFilters = () => {
    setSearch('');
    setSearchInput('');
    setInputTypeFilter('');
    setStatusFilter('');
    setPage(1);
  };

  const hasFilters = search || inputTypeFilter || statusFilter;

  // Export all pages as CSV
  const exportCSV = async () => {
    try {
      setIsExporting(true);
      let allVideos = [];
      let p = 1;
      let pages = 1;
      const SIZE = 500;

      do {
        const json = await api.videos({ ...queryParams, page: p, page_size: SIZE });
        if (Array.isArray(json?.data)) allVideos.push(...json.data);
        pages = json?.pages || 1;
        p++;
      } while (p <= pages);

      const headers = ['Video ID', 'Headline', 'Uploaded By', 'Input Type', 'Status', 'Platform', 'Published URL'];
      const rows = [
        headers.join(','),
        ...allVideos.map(row => [
          row.video_id,
          `"${(row.headline || '').replace(/"/g, '""')}"`,
          `"${row.uploaded_by}"`,
          row.input_type,
          row.is_published ? 'Published' : 'Not Published',
          row.published_platform,
          row.published_url,
        ].join(',')),
      ];

      const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = 'videos.csv';
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error("CSV export error:", e);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <DashboardLayout title="Video Explorer">
      <div className="space-y-4">

        {/* Search + filters bar */}
        <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
          <div className="flex-1 w-full flex gap-2">
            <AiSearchBar
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') applySearch(); }}
              placeholder="Search by headline…"
            />
            <Button variant="outline" onClick={applySearch}>Search</Button>
          </div>

          {/* Input type filter */}
          <Select value={inputTypeFilter} onValueChange={v => { setInputTypeFilter(v === 'all' ? '' : v); setPage(1); }}>
            <SelectTrigger className="w-44 h-11">
              <SelectValue placeholder="All input types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All input types</SelectItem>
              {inputTypes.map(t => (
                <SelectItem key={t.input_type} value={t.input_type}>
                  {t.input_type}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Published status filter */}
          <Select value={statusFilter} onValueChange={v => { setStatusFilter(v === 'all' ? '' : v); setPage(1); }}>
            <SelectTrigger className="w-40 h-11">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="published">Published</SelectItem>
              <SelectItem value="unpublished">Not Published</SelectItem>
            </SelectContent>
          </Select>

          {hasFilters && (
            <Button variant="ghost" size="sm" onClick={clearFilters} className="shrink-0">
              <X className="h-4 w-4 mr-1" /> Clear
            </Button>
          )}

          <Button variant="outline" onClick={exportCSV} disabled={isExporting} className="shrink-0">
            <Download className="mr-2 h-4 w-4" />
            {isExporting ? 'Exporting…' : 'Export CSV'}
          </Button>
        </div>

        {/* Total count */}
        {total > 0 && (
          <p className="text-xs text-muted-foreground">
            {total.toLocaleString()} video{total !== 1 ? 's' : ''} found
          </p>
        )}

        {/* Table */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border bg-card overflow-hidden"
        >
          {isLoading ? (
            <div className="p-8 text-center text-muted-foreground text-sm">Loading…</div>
          ) : videos.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground text-sm">No videos match your filters.</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Video ID</TableHead>
                  <TableHead>Headline</TableHead>
                  <TableHead>Uploaded By</TableHead>
                  <TableHead>Input Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Platform</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {videos.map(v => (
                  <TableRow key={v.video_id}>
                    <TableCell className="font-mono text-xs text-muted-foreground">{v.video_id}</TableCell>
                    <TableCell className="font-medium max-w-xs truncate" title={v.headline}>{v.headline}</TableCell>
                    <TableCell>{v.uploaded_by}</TableCell>
                    <TableCell className="capitalize">{v.input_type}</TableCell>
                    <TableCell><StatusBadge status={v.is_published ? 'Published' : 'Not Published'} /></TableCell>
                    <TableCell className="text-sm text-muted-foreground">{v.published_platform}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </motion.div>

        {/* Pagination */}
        <div className="flex items-center justify-end gap-2">
          <Button variant="outline" size="sm"
            onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <Button variant="outline" size="sm"
            onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>

      </div>
    </DashboardLayout>
  );
}
