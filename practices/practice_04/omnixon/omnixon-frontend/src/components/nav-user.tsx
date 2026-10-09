import { useNavigate } from 'react-router-dom'
import { useTheme } from 'next-themes'
import { BotIcon, ChevronsUpDownIcon, KeyRoundIcon, LogOutIcon, MonitorIcon, MoonIcon, SettingsIcon, SunIcon } from 'lucide-react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { SidebarMenu, SidebarMenuButton, SidebarMenuItem, useSidebar } from '@/components/ui/sidebar'
import { useAuth } from '@/lib/auth'
import { t } from '@/lib/i18n'

export function NavUser() {
  const { isMobile } = useSidebar()
  const { token, isAdmin, logout } = useAuth()
  const { setTheme } = useTheme()
  const navigate = useNavigate()
  const name = token?.name ?? t('Token')
  const detail = token?.is_initial ? t('{role}, initial', { role: token.role }) : (token?.role ?? '')

  const identity = (
    <>
      <Avatar>
        <AvatarFallback>
          <KeyRoundIcon className="size-4" />
        </AvatarFallback>
      </Avatar>
      <div className="grid flex-1 text-left text-sm leading-tight">
        <span className="truncate font-medium">{name}</span>
        <span className="truncate text-xs text-muted-foreground">{detail}</span>
      </div>
    </>
  )

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger render={<SidebarMenuButton size="lg" className="aria-expanded:bg-muted" />}>
            {identity}
            <ChevronsUpDownIcon className="ml-auto size-4" />
          </DropdownMenuTrigger>
          <DropdownMenuContent className="min-w-56 rounded-lg" side={isMobile ? 'bottom' : 'right'} align="end" sideOffset={4}>
            <DropdownMenuGroup>
              <DropdownMenuLabel className="p-0 font-normal">
                <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">{identity}</div>
              </DropdownMenuLabel>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              {token && (isAdmin || token.role === 'user') && (
                <DropdownMenuItem onClick={() => navigate(`/agents/${token.agent_id}`)}>
                  <BotIcon /> {t('My agent')}
                </DropdownMenuItem>
              )}
              <DropdownMenuItem onClick={() => navigate('/settings')}>
                <SettingsIcon /> {t('Settings')}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setTheme('light')}>
                <SunIcon /> {t('Light theme')}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setTheme('dark')}>
                <MoonIcon /> {t('Dark theme')}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setTheme('system')}>
                <MonitorIcon /> {t('System theme')}
              </DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={logout}>
              <LogOutIcon /> {t('Sign out')}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
