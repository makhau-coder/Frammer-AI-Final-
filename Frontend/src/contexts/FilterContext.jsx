/**
 * src/contexts/FilterContext.jsx
 *
 * REWRITE: Removed all mockData dependency.
 *
 * FilterContext is now a pure state container for filter values.
 * Pages use these values to build API query params and pass them to
 * api.videos(), api.channels(), etc.
 *
 * No client-side filtering happens here — filtering is server-side.
 */

import React, { createContext, useContext, useState } from 'react';

const defaultFilters = {
  search:        '',
  inputType:     '',
  outputType:    '',
  language:      '',
  platform:      '',
  publishedStatus: '',  // 'published' | 'not_published' | ''
};

const FilterContext = createContext(undefined);

export function FilterProvider({ children }) {
  const [filters, setFilters] = useState(defaultFilters);

  const updateFilter = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const clearFilters = () => setFilters(defaultFilters);

  const activeCount = Object.values(filters).filter(Boolean).length;

  /**
   * Converts the current filter state into query params for api.videos().
   * Usage in any page:
   *   const { toVideoParams } = useFilters();
   *   const { data } = useQuery({ queryFn: () => api.videos({ page, ...toVideoParams() }) });
   */
  const toVideoParams = () => {
    const params = {};
    if (filters.search)          params.search        = filters.search;
    if (filters.inputType)       params.input_type    = filters.inputType;
    if (filters.platform)        params.platform      = filters.platform;
    if (filters.publishedStatus) params.is_published  = filters.publishedStatus === 'published';
    return params;
  };

  return (
    <FilterContext.Provider value={{
      filters,
      setFilters,
      updateFilter,
      clearFilters,
      activeCount,
      toVideoParams,
    }}>
      {children}
    </FilterContext.Provider>
  );
}

export function useFilters() {
  const ctx = useContext(FilterContext);
  if (!ctx) throw new Error('useFilters must be used within FilterProvider');
  return ctx;
}
