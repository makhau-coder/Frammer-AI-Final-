import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { AiSearchBar } from '@/components/ui/AiSearchBar';
import { StatusBadge } from '@/components/ui/StatusBadge';
import {Table,TableBody,TableCell,TableHead,TableHeader,TableRow,} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Download, ChevronLeft, ChevronRight } from 'lucide-react';

export default function VideoExplorer() {
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [isExporting, setIsExporting] = useState(false);
  const [search, setSearch] = useState(''); // Note: Backend filters are precise (uploader, input_type), not generic search. Using this as placeholder or could map to one.

  // Fetch videos with pagination
  // Note: search in backend is specific (uploaded_by, etc). 
  // For now, we fetch basic paginated list. To implement search, we'd need to map search term to 'uploaded_by' param etc.
  const { data } = useQuery({
    queryKey: ['videos', page, pageSize],
    queryFn: async () => {
      const res = await fetch(`http://localhost:8000/api/videos?page=${page}&page_size=${pageSize}`);
      if (!res.ok) return { data: [], pages: 1 };
      return res.json();
    },
    keepPreviousData: true
  });

  const videos = Array.isArray(data?.data) ? data.data : [];
  const totalPages = data?.pages || 1;

  const exportCSV = async () => {
    try {
      setIsExporting(true);
      let allVideos = [];
      let currentPage = 1;
      let totalExportPages = 1;
      const exportPageSize = 100; // Use a safe page size to prevent 422 validation errors

      // Loop through all pages and aggregate the data
      do {
        const res = await fetch(`http://localhost:8000/api/videos?page=${currentPage}&page_size=${exportPageSize}`);
        if (!res.ok) throw new Error(`Failed to fetch videos on page ${currentPage}`);
        
        const json = await res.json();
        if (Array.isArray(json?.data)) allVideos.push(...json.data);
        totalExportPages = json?.pages || 1;
        currentPage++;
      } while (currentPage <= totalExportPages);

      const headers = ['Video ID', 'Headline', 'Uploaded By', 'Input Type', 'Status', 'Platform', 'Published URL'];
      const csvRows = [
        headers.join(','),
        ...allVideos.map(row => [
          row.video_id,
          `"${(row.headline || '').replace(/"/g, '""')}"`,
          `"${row.uploaded_by}"`,
          row.input_type,
          row.is_published ? 'Published' : 'Not Published',
          row.published_platform,
          row.published_url
        ].join(','))
      ];
      const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'all_videos.csv';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Error exporting CSV:", error);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <DashboardLayout title="Video Explorer">
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
          <div className="flex-1 w-full">
            <AiSearchBar placeholder="Search functionality requires backend update..." disabled />
          </div>
          <Button variant="outline" onClick={exportCSV} disabled={isExporting} className="shrink-0">
            <Download className="mr-2 h-4 w-4" />
            {isExporting ? 'Exporting...' : 'Export CSV'}
          </Button>
        </div>

        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="rounded-xl border bg-card card-shadow overflow-hidden">
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
              {videos.map((video) => (
                <TableRow key={video.video_id}>
                  <TableCell className="font-mono text-xs text-muted-foreground">{video.video_id}</TableCell>
                  <TableCell className="font-medium max-w-xs truncate" title={video.headline}>{video.headline}</TableCell>
                  <TableCell>{video.uploaded_by}</TableCell>
                  <TableCell className="capitalize">{video.input_type}</TableCell>
                  <TableCell><StatusBadge status={video.is_published ? 'Published' : 'Not Published'} /></TableCell>
                  <TableCell className="text-sm text-muted-foreground">{video.published_platform}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </motion.div>

        <div className="flex items-center justify-end gap-2">
            <Button 
                variant="outline" 
                size="sm" 
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
            >
                <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm text-muted-foreground">
                Page {page} of {totalPages}
            </span>
            <Button 
                variant="outline" 
                size="sm" 
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
            >
                <ChevronRight className="h-4 w-4" />
            </Button>
        </div>
      </div>
    </DashboardLayout>
  );
}
