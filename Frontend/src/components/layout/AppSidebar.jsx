import {
  LayoutDashboard, TrendingUp, Users, Layers, Table2,
  PanelLeftClose, PanelLeft
} from 'lucide-react';
import { NavLink } from '@/components/NavLink';
import { useLocation } from 'react-router-dom';
import {
  Sidebar, SidebarContent, SidebarGroup, SidebarGroupContent,
  SidebarGroupLabel, SidebarMenu, SidebarMenuButton, SidebarMenuItem,
  useSidebar,
} from '@/components/ui/sidebar';

const items = [
  { title: 'Executive Overview', url: '/', icon: LayoutDashboard },
  { title: 'Usage & Trends', url: '/usage', icon: TrendingUp },
  { title: 'Client Analysis', url: '/clients', icon: Users },
  { title: 'Multi-Dimensional', url: '/multi', icon: Layers },
  { title: 'Video Explorer', url: '/explorer', icon: Table2 },
];

export function AppSidebar() {
  const { state, toggleSidebar } = useSidebar();
  const collapsed = state === 'collapsed';
  const location = useLocation();

  return (
    <Sidebar collapsible="icon" className="border-none bg-sidebar">
      <SidebarContent>
        <div className="flex items-center justify-center gap-2 px-4 py-4">
          {!collapsed && (
            <img src="src/components/ui/logo.png" alt="FramerAI" className="h-7 mt-1.5 mr-7" />
          )}
        </div>
        <SidebarGroup>
          <SidebarGroupLabel className="mb-1.5" >ANALYTICS</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild className="py-5">
                    <NavLink
                      to={item.url}
                      end={item.url === '/'}
                      className="text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground text-base"
                      activeClassName="bg-sidebar-accent text-sidebar-foreground font-medium text-base"
                    >
                      <item.icon className="mr-2 h-4 w-4" />
                      {!collapsed && <span>{item.title}</span>}
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}
