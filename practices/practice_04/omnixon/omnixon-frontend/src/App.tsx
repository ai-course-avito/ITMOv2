import { lazy, type ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation, useSearchParams } from 'react-router-dom'
import { Layout } from '@/components/layout'
import { canOpen, homePath } from '@/components/nav-items'
import { Spinner } from '@/components/ui/spinner'
import { signedOut, useAuth } from '@/lib/auth'
import Landing from '@/pages/landing'
import Login from '@/pages/login'

// The front page and the sign-in are what a visitor needs; every page behind them is loaded when it is opened (the chart, graph and
// highlighter libraries are not part of the first load)
const Dashboard = lazy(() => import('@/pages/dashboard'))
const Metrics = lazy(() => import('@/pages/metrics'))
const Chat = lazy(() => import('@/pages/chat'))
const Agents = lazy(() => import('@/pages/agents'))
const AgentDetail = lazy(() => import('@/pages/agent-detail'))
const Models = lazy(() => import('@/pages/models'))
const McpServers = lazy(() => import('@/pages/mcp-servers'))
const Rag = lazy(() => import('@/pages/rag'))
const Memories = lazy(() => import('@/pages/memories'))
const UsersPage = lazy(() => import('@/pages/users'))
const Tokens = lazy(() => import('@/pages/tokens'))
const AgentGraph = lazy(() => import('@/pages/agent-graph'))
const Usage = lazy(() => import('@/pages/usage'))
const SettingsPage = lazy(() => import('@/pages/settings'))

/** `/` leads to where the role starts (see homePath). */
function Home() {
  const { role } = useAuth()
  return <Navigate to={homePath(role)} replace />
}

/** A page the role is not offered goes back to the start of the role (the service would refuse its calls anyway). */
function Gate({ path, children }: { path: string; children: ReactNode }) {
  const { role } = useAuth()
  return canOpen(role, path) ? children : <Navigate to="/" replace />
}

/** Signed in at /login: on to where the visitor was going. */
function AfterLogin() {
  const [params] = useSearchParams()
  const next = params.get('next')
  return <Navigate to={next && next.startsWith('/') && !next.startsWith('//') ? next : '/'} replace />
}

function ToLogin() {
  const { pathname, search } = useLocation()
  if (signedOut.now) {
    signedOut.now = false
    return <Navigate to="/" replace />
  }
  return <Navigate to={`/login?next=${encodeURIComponent(pathname + search)}`} replace />
}

function MyAgent() {
  const { agentId } = useAuth()
  return <Navigate to={agentId !== undefined ? `/agents/${agentId}` : '/'} replace />
}

export default function App() {
  const { status } = useAuth()
  if (status === 'checking')
    return (
      <div className="flex min-h-svh items-center justify-center">
        <Spinner />
      </div>
    )
  return (
    <BrowserRouter>
      <Routes>
        {status === 'out' ? (
          <>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="*" element={<ToLogin />} />
          </>
        ) : (
          <Route element={<Layout />}>
            <Route index element={<Home />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="login" element={<AfterLogin />} />
            <Route path="chat" element={<Chat />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route
              path="my-agent"
              element={
                <Gate path="/my-agent">
                  <MyAgent />
                </Gate>
              }
            />
            <Route
              path="metrics"
              element={
                <Gate path="/metrics">
                  <Metrics />
                </Gate>
              }
            />
            <Route
              path="usage"
              element={
                <Gate path="/usage">
                  <Usage />
                </Gate>
              }
            />
            <Route
              path="agents"
              element={
                <Gate path="/agents">
                  <Agents />
                </Gate>
              }
            />
            <Route
              path="agents/:id"
              element={
                <Gate path="/agents/1">
                  <AgentDetail />
                </Gate>
              }
            />
            <Route
              path="agent-graph"
              element={
                <Gate path="/agent-graph">
                  <AgentGraph />
                </Gate>
              }
            />
            <Route
              path="models"
              element={
                <Gate path="/models">
                  <Models />
                </Gate>
              }
            />
            <Route
              path="mcp-servers"
              element={
                <Gate path="/mcp-servers">
                  <McpServers />
                </Gate>
              }
            />
            <Route
              path="rag"
              element={
                <Gate path="/rag">
                  <Rag />
                </Gate>
              }
            />
            <Route
              path="memories"
              element={
                <Gate path="/memories">
                  <Memories />
                </Gate>
              }
            />
            <Route
              path="users"
              element={
                <Gate path="/users">
                  <UsersPage />
                </Gate>
              }
            />
            <Route
              path="tokens"
              element={
                <Gate path="/tokens">
                  <Tokens />
                </Gate>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        )}
      </Routes>
    </BrowserRouter>
  )
}
