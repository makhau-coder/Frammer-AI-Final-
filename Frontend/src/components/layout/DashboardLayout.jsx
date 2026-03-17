import { SidebarProvider } from '@/components/ui/sidebar';
import { AppSidebar } from './AppSidebar';
import { Header } from './Header';
import { Chatbot } from '@/components/chatbot/Chatbot';

export function DashboardLayout({ title, children }) {
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
      <Chatbot />
    </SidebarProvider>
  );
}
