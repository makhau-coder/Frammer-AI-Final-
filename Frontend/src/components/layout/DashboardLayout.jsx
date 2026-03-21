// src/components/layout/DashboardLayout.jsx
//
// Renders the full shell (sidebar + header + main content).
// Chatbot is shown on every page EXCEPT the AI Chat page itself
// (to avoid having two chat interfaces at once).
//
// The Chatbot component reads useLocation() internally and switches
// its page context automatically — no props needed here.

import { useLocation } from 'react-router-dom';
import { SidebarProvider } from '@/components/ui/sidebar';
import { AppSidebar } from './AppSidebar';
import { Header } from './Header';
import { Chatbot } from '@/components/chatbot/Chatbot';

export function DashboardLayout({ title, children }) {
  const { pathname } = useLocation();

  // Hide the floating chatbot on the dedicated AI Chat page
  const showChatbot = pathname !== '/chat';

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full">
        <AppSidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <Header title={title} />
          <main className="flex-1 overflow-auto p-4 md:p-6 pt-2 md:pt-3">
            {children}
          </main>
        </div>
      </div>
      {showChatbot && <Chatbot />}
    </SidebarProvider>
  );
}