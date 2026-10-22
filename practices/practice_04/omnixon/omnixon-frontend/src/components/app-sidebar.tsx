import type { ComponentProps } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '@/lib/auth'
import { t } from '@/lib/i18n'
import { NavMain } from '@/components/nav-main'
import { groupsFor, settingsItem } from '@/components/nav-items'
import { NavSecondary } from '@/components/nav-secondary'
import { Logo } from '@/components/logo'
import { NavUser } from '@/components/nav-user'
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarMenu, SidebarMenuButton, SidebarMenuItem } from '@/components/ui/sidebar'

export function AppSidebar(props: ComponentProps<typeof Sidebar>) {
  const { role, isAdmin } = useAuth()
  return (
    <Sidebar variant="inset" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" render={<NavLink to="/" />}>
              <Logo />
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-medium">Omnixon</span>
                <span className="truncate text-xs text-muted-foreground">{isAdmin ? t('Admin panel') : role === 'user' ? t('Agent panel') : t('Playground')}</span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        {groupsFor(role).map((g) => (
          <NavMain key={g.label} label={g.label} items={g.items} />
        ))}
        <NavSecondary items={[settingsItem]} className="mt-auto" />
      </SidebarContent>
      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
    </Sidebar>
  )
}
