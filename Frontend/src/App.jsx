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
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const App = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Sonner />
          <BrowserRouter>
            <Routes>
              {/* Removed the summary prop here */}
              <Route path="/" element={<ExecutiveOverview />} />
              <Route path="/usage" element={<UsageTrends />} />
              <Route path="/clients" element={<ClientAnalysis />} />
              <Route path="/multi" element={<MultiDimensionalAnalysis />} />
              <Route path="/explorer" element={<VideoExplorer />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
  );
};

export default App;