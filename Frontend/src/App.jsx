// ════════════════════════════════════════════════════════
// FILE 1:  src/App.jsx  — add DataQuality route
// ════════════════════════════════════════════════════════

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import ExecutiveOverview from "./pages/ExecutiveOverview";
import UsageTrends from "./pages/UsageTrends";
import ClientAnalysis from "./pages/ClientAnalysis";
import MultiDimensionalAnalysis from "./pages/MultiDimensionalAnalysis";
import VideoExplorer from "./pages/VideoExplorer";
import ChatbotPage from "./pages/ChatbotPage";
import DataQualityPage from "./pages/DataQualityPage";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime:            60_000,
      retry:                1,
      refetchOnWindowFocus: false,
    },
  },
});

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster /><Sonner />
      <BrowserRouter>
        <Routes>
          <Route path="/"            element={<ExecutiveOverview />} />
          <Route path="/usage"       element={<UsageTrends />} />
          <Route path="/clients"     element={<ClientAnalysis />} />
          <Route path="/multi"       element={<MultiDimensionalAnalysis />} />
          <Route path="/explorer"    element={<VideoExplorer />} />
          <Route path="/chat"        element={<ChatbotPage />} />
          <Route path="/data-quality" element={<DataQualityPage />} />
          <Route path="*"            element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
