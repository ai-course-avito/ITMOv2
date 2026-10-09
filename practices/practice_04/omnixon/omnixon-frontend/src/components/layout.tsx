import { Fragment, Suspense } from 'react'
import { LoadingRows } from '@/components/page'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { AppSidebar } from '@/components/app-sidebar'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { Separator } from '@/components/ui/separator'
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'
import { t } from '@/lib/i18n'

const titles: Record<string, string> = {
  chat: 'Playground',
  metrics: 'Metrics',
  agents: 'Agents',
  models: 'Models',
  'mcp-servers': 'MCP servers',
  'agent-graph': 'Agent graph',
  rag: 'Knowledge base',
  memories: 'Memories',
  users: 'Users & history',
  tokens: 'Tokens',
  usage: 'Usage',
  'my-agent': 'My agent',
  settings: 'Settings',
  dashboard: 'Dashboard',
}

function useCrumbs() {
  const parts = useLocation().pathname.split('/').filter(Boolean)
  // an entity's page is called by its name, not its id (shares the cache of the page itself)
  const agentId = parts[0] === 'agents' && parts[1] ? Number(parts[1]) : null
  const agent = useQuery({
    queryKey: ['agent', agentId],
    queryFn: () => api.agent(agentId!),
    enabled: agentId !== null && Number.isInteger(agentId),
  })
  const crumbs = [{ label: 'Omnixon', to: '/' }]
  if (!parts.length) return [{ label: t('Dashboard'), to: '/' }]
  crumbs.push({ label: titles[parts[0]] ? t(titles[parts[0]]) : parts[0], to: `/${parts[0]}` })
  if (parts[1]) crumbs.push({ label: agent.data?.name ?? parts[1], to: `/${parts[0]}/${parts[1]}` })
  return crumbs
}

export function Layout() {
  const crumbs = useCrumbs()
  return (
    <SidebarProvider className="h-svh">
      <AppSidebar />
      <SidebarInset className="h-svh min-h-0 min-w-0 overflow-hidden md:h-[calc(100svh-(--spacing(4)))]">
        <header className="flex h-14 shrink-0 items-center gap-2">
          <div className="flex items-center gap-2 px-4">
            <SidebarTrigger className="-ml-1" />
            <Separator orientation="vertical" className="mr-2 data-vertical:h-4 data-vertical:self-auto" />
            <Breadcrumb>
              <BreadcrumbList>
                {crumbs.map((c, i) => (
                  <Fragment key={c.to}>
                    {i > 0 && <BreadcrumbSeparator />}
                    <BreadcrumbItem>
                      {i === crumbs.length - 1 ? (
                        <BreadcrumbPage>{c.label}</BreadcrumbPage>
                      ) : (
                        <BreadcrumbLink render={<Link to={c.to} />}>{c.label}</BreadcrumbLink>
                      )}
                    </BreadcrumbItem>
                  </Fragment>
                ))}
              </BreadcrumbList>
            </Breadcrumb>
          </div>
        </header>
        {/* the page fills what is left under the bar; pages that are long scroll inside it */}
        <div className="flex min-h-0 flex-1 flex-col px-4 pb-4 md:px-6 md:pb-6">
          <Suspense fallback={<LoadingRows rows={4} />}>
            <Outlet />
          </Suspense>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
