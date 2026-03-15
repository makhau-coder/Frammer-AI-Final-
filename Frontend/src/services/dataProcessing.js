import { format, parseISO, startOfWeek, startOfMonth } from 'date-fns';

export function getUploadedCount(videos) { return videos.length; }
export function getProcessedCount(videos) { return videos.filter(v => v.processed_at).length; }
export function getPublishedCount(videos) { return videos.filter(v => v.published_flag).length; }
export function getTotalDuration(videos) { return videos.reduce((s, v) => s + v.duration, 0); }
export function getProcessedDuration(videos) {
  return videos.filter(v => v.processed_at).reduce((s, v) => s + v.duration, 0);
}
export function getPublishedDuration(videos) {
  return videos.filter(v => v.published_flag).reduce((s, v) => s + v.duration, 0);
}
export function getPublishRate(videos) {
  const processed = getProcessedCount(videos);
  return processed > 0 ? getPublishedCount(videos) / processed : 0;
}
export function formatDuration(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}
export function formatHours(seconds) {
  return (seconds / 3600).toFixed(1) + 'h';
}

export function groupByTime(videos, dateField, granularity) {
  const groups = {};
  videos.forEach(v => {
    const val = v[dateField];
    if (!val || typeof val !== 'string') return;
    const d = parseISO(val);
    let key;
    if (granularity === 'day') key = format(d, 'yyyy-MM-dd');
    else if (granularity === 'week') key = format(startOfWeek(d), 'yyyy-MM-dd');
    else key = format(startOfMonth(d), 'yyyy-MM');
    groups[key] = (groups[key] || 0) + 1;
  });
  return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b)).map(([date, count]) => ({ date, count }));
}

export function groupByDimension(videos, dimension) {
  const groups = {};
  videos.forEach(v => {
    const key = v[dimension];
    if (!key) return;
    if (!groups[key]) groups[key] = [];
    groups[key].push(v);
  });
  return groups;
}

export function getGrowthPercent(current, previous) {
  if (previous === 0) return current > 0 ? 100 : 0;
  return ((current - previous) / previous) * 100;
}

export function generateSparkline(videos, days = 7) {
  const now = new Date();
  const data = [];
  for (let i = days - 1; i >= 0; i--) {
    const day = new Date(now);
    day.setDate(day.getDate() - i);
    const dayStr = format(day, 'yyyy-MM-dd');
    data.push(videos.filter(v => format(parseISO(v.uploaded_at), 'yyyy-MM-dd') === dayStr).length);
  }
  return data;
}
