import { NavLink, useLocation } from 'react-router-dom'
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar'
import type { NavItem } from '@/components/nav-items'

export function NavMain({ label, items }: { label: string; items: NavItem[] }) {
  const { pathname } = useLocation()
  return (
    <SidebarGroup>
      <SidebarGroupLabel>{label}</SidebarGroupLabel>
      <SidebarMenu>
        {items.map((item) => {
          const active = pathname.startsWith(item.url)
          return (
            <SidebarMenuItem key={item.url}>
              <SidebarMenuButton isActive={active} tooltip={item.title} render={<NavLink to={item.url} />}>
                {item.icon}
                <span>{item.title}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          )
        })}
      </SidebarMenu>
    </SidebarGroup>
  )
}
