import React, { createContext, useContext, useState, useMemo } from 'react';
import { videos as allVideos } from '@/data/mockData';
import { isWithinInterval, parseISO } from 'date-fns';

const defaultFilters = {
  dateRange: { from: new Date('2025-09-01'), to: new Date('2026-03-10') },
  comparisonDateRange: null,
  client: [],
  channel: [],
  user: [],
  language: [],
  inputType: [],
  outputType: [],
  publishedStatus: [],
  platform: [],
  team: [],
};

const FilterContext = createContext(undefined);

function applyFilters(videos, filters, dateRange) {
  return videos.filter((v) => {
    const uploadDate = parseISO(v.uploaded_at);
    if (!isWithinInterval(uploadDate, { start: dateRange.from, end: dateRange.to })) return false;
    if (filters.client.length && !filters.client.includes(v.client_id)) return false;
    if (filters.channel.length && !filters.channel.includes(v.channel_id)) return false;
    if (filters.user.length && !filters.user.includes(v.user_id)) return false;
    if (filters.language.length && !filters.language.includes(v.language)) return false;
    if (filters.inputType.length && !filters.inputType.includes(v.input_type)) return false;
    if (filters.outputType.length && !filters.outputType.includes(v.output_type)) return false;
    if (filters.platform.length && v.published_platform && !filters.platform.includes(v.published_platform)) return false;
    if (filters.team.length && !filters.team.includes(v.team_name)) return false;
    if (filters.publishedStatus.length) {
      const status = v.published_flag ? 'Published' : 'Unpublished';
      if (!filters.publishedStatus.includes(status)) return false;
    }
    return true;
  });
}

export function FilterProvider({ children }) {
  const [filters, setFilters] = useState(defaultFilters);

  const filteredVideos = useMemo(
    () => applyFilters(allVideos, filters, filters.dateRange),
    [filters]
  );

  const comparisonVideos = useMemo(
    () => filters.comparisonDateRange
      ? applyFilters(allVideos, filters, filters.comparisonDateRange)
      : [],
    [filters]
  );

  return (
    <FilterContext.Provider value={{ filters, setFilters, filteredVideos, comparisonVideos }}>
      {children}
    </FilterContext.Provider>
  );
}

export function useFilters() {
  const ctx = useContext(FilterContext);
  if (!ctx) throw new Error('useFilters must be used within FilterProvider');
  return ctx;
}
