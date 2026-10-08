import type { ReactNode } from 'react'
import {
  ActivityIcon,
  ChartColumnIcon,
  BookOpenIcon,
  BotIcon,
  BrainIcon,
  CpuIcon,
  WorkflowIcon,
  KeyRoundIcon,
  LayoutDashboardIcon,
  MessageSquareIcon,
  PlugIcon,
  SettingsIcon,
  UsersIcon,
} from 'lucide-react'
import { rankOf, type Role } from '@/lib/types'

export interface NavItem {
  title: string
  url: string
  icon: ReactNode
  /** One line for the cards on the dashboard. */
  description: string
  /** The lowest role that is offered this page (the service decides what is really allowed). */
  minRole: Role
  /** Only this role is offered it (the page of "your agent" is for a user token; an admin has the list of agents). */
  onlyRole?: Role
}

export interface NavGroup {
  label: string
  items: NavItem[]
}

/** Where everything is: the sidebar, the dashboard cards and the routes all read this. */
export const navGroups: NavGroup[] = [
  {
    label: 'Overview',
    items: [
      {
        title: 'Dashboard',
        url: '/dashboard',
        icon: <LayoutDashboardIcon />,
        description: 'Service health and a summary',
        minRole: 'regular',
      },
      {
        title: 'Playground',
        url: '/chat',
        icon: <MessageSquareIcon />,
        description: 'Talk to an agent, with files and voice, over JSON or SSE',
        minRole: 'regular',
      },
      {
        title: 'Usage',
        url: '/usage',
        icon: <ChartColumnIcon />,
        description: 'What each token spent on the models',
        minRole: 'user',
      },
      {
        title: 'Metrics',
        url: '/metrics',
        icon: <ActivityIcon />,
        description: 'Prometheus samples of the service',
        minRole: 'admin',
      },
    ],
  },
  {
    label: 'Behaviour',
    items: [
      {
        title: 'My agent',
        url: '/my-agent',
        icon: <BotIcon />,
        description: 'Prompt, model, tools, MCP servers, versions',
        minRole: 'user',
        onlyRole: 'user',
      },
      {
        title: 'Agents',
        url: '/agents',
        icon: <BotIcon />,
        description: 'Prompts, tools, limits, versions and rollback',
        minRole: 'admin',
      },
      {
        title: 'Agent graph',
        url: '/agent-graph',
        icon: <WorkflowIcon />,
        description: 'Which agent may call which, and what for',
        minRole: 'admin',
      },
      {
        title: 'Models',
        url: '/models',
        icon: <CpuIcon />,
        description: 'OpenRouter request bodies agents run on',
        minRole: 'admin',
      },
      {
        title: 'MCP servers',
        url: '/mcp-servers',
        icon: <PlugIcon />,
        description: 'External tool servers for agents',
        minRole: 'admin',
      },
    ],
  },
  {
    label: 'Data',
    items: [
      {
        title: 'Knowledge base',
        url: '/rag',
        icon: <BookOpenIcon />,
        description: 'Per-agent entries found by meaning',
        minRole: 'user',
      },
      {
        title: 'Memories',
        url: '/memories',
        icon: <BrainIcon />,
        description: 'What the model remembers about a user',
        minRole: 'user',
      },
      {
        title: 'Users & history',
        url: '/users',
        icon: <UsersIcon />,
        description: 'Look a user up, read or clear their history',
        minRole: 'regular',
      },
    ],
  },
  {
    label: 'Access',
    items: [
      {
        title: 'Tokens',
        url: '/tokens',
        icon: <KeyRoundIcon />,
        description: 'Who may use an agent, and as what',
        minRole: 'user',
      },
    ],
  },
]

export const settingsItem: NavItem = {
  title: 'Settings',
  url: '/settings',
  icon: <SettingsIcon />,
  description: 'Connection and appearance',
  minRole: 'regular',
}

const offered = (item: NavItem, role: Role | undefined) =>
  rankOf(role) >= rankOf(item.minRole) && (!item.onlyRole || item.onlyRole === role)

/** The groups a role is offered. */
export function groupsFor(role: Role | undefined): NavGroup[] {
  return navGroups.map((g) => ({ ...g, items: g.items.filter((i) => offered(i, role)) })).filter((g) => g.items.length)
}

/** Whether a role may open this path (the page of an agent, `/agents/:id`, is open to a user: its own, which the service checks). */
export function canOpen(role: Role | undefined, path: string): boolean {
  const all = [...navGroups.flatMap((g) => g.items), settingsItem]
  const item = all.find((i) => i.url === path)
  if (item) return offered(item, role)
  if (path.startsWith('/agents/')) return rankOf(role) >= rankOf('user')
  return false
}

/** Where a role starts: regular and user tokens are for trying their own model, so they open on the Playground;
 *  the state of the service matters more to admin and owner. The dashboard is still in the sidebar for everyone. */
export const homePath = (role: Role | undefined) => (rankOf(role) <= rankOf('user') ? '/chat' : '/dashboard')
