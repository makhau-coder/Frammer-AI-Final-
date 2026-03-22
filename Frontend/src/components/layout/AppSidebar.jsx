import {
  LayoutDashboard, TrendingUp, Users, Layers,
  Table2, MessageSquare, ShieldCheck
} from "lucide-react";
import { NavLink } from "@/components/NavLink";
import {
  Sidebar, SidebarContent, SidebarGroup, SidebarGroupContent,
  SidebarGroupLabel, SidebarMenu, SidebarMenuButton, SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";

const items = [
  { title: "Executive Overview", url: "/", icon: LayoutDashboard },
  { title: "Usage & Trends", url: "/usage", icon: TrendingUp },
  { title: "Client Analysis", url: "/clients", icon: Users },
  { title: "Multi-Dimensional", url: "/multi", icon: Layers },
  { title: "Video Explorer", url: "/explorer", icon: Table2 },
  { title: "AI Chat", url: "/chat", icon: MessageSquare },
  { title: "Data Quality", url: "/data-quality", icon: ShieldCheck },
];

export function AppSidebar() {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";

  return (
    <Sidebar collapsible="icon" className="border-none bg-sidebar">
      <SidebarContent>
        <div className="flex items-center justify-center px-4 h-16">
          <img 
            src="../public/logo.png" 
            alt="Frammer AI" 
            className={`h-7 mt-1.5 transition-all duration-300 object-contain object-left ${
              collapsed ? "max-w-0 opacity-0 mr-0" : "max-w-[150px] opacity-100 mr-7"
            }`} 
          />
        </div>
        <SidebarGroup>
          <SidebarGroupLabel 
            className={`mb-1.5 overflow-hidden whitespace-nowrap transition-all duration-300 ${
              collapsed ? "max-w-0 opacity-0" : "max-w-[200px] opacity-100"
            }`}
          >
            ANALYTICS
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild className="py-5">
                    <NavLink
                      to={item.url}
                      end={item.url === "/"}
                      className="text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground text-base flex items-center"
                      activeClassName="bg-sidebar-accent text-sidebar-foreground font-medium text-base"
                    >
                      <item.icon className={`h-4 w-4 shrink-0 transition-all duration-300 ${collapsed ? "mr-0" : "mr-2"}`} />
                      <span 
                        className={`overflow-hidden whitespace-nowrap transition-all duration-300 ${
                          collapsed ? "max-w-0 opacity-0" : "max-w-[200px] opacity-100"
                        }`}
                      >
                        {item.title}
                      </span>
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
