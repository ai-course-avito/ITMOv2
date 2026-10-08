import { Link } from 'react-router-dom'
import { useTheme } from 'next-themes'
import {
  BookOpenIcon,
  BrainIcon,
  ChartColumnIcon,
  FileAudioIcon,
  GitBranchIcon,
  KeyRoundIcon,
  LayersIcon,
  MoonIcon,
  PlugIcon,
  ShieldCheckIcon,
  SunIcon,
  ZapIcon,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { CodeBlock } from '@/components/code-block'
import AnimatedContent from '@/components/AnimatedContent'
import DotField from '@/components/DotField'
import BlurText from '@/components/BlurText'
import CountUp from '@/components/CountUp'
import LogoLoop from '@/components/LogoLoop'
import { ConnectionsGraph } from '@/components/connections-graph'
import { Logo } from '@/components/logo'
import SpotlightCard from '@/components/SpotlightCard'
import TechText from '@/components/TechText'
import TextType from '@/components/TextType'

const FEATURES = [
  { icon: ZapIcon, title: 'One chat API', text: 'Send a message for a user and get the answer as JSON or as a server-sent-events stream. The same call for a Telegram bot, a website or a script.' },
  { icon: LayersIcon, title: 'Any model, one place', text: 'Models are OpenRouter request bodies, so hundreds of models and every provider option work without code. Switch an agent to another model with one change.' },
  { icon: BrainIcon, title: 'Memory that lasts', text: 'The model remembers lasting facts about each user, finds them by meaning, and forgets what is outdated. It learns in the background after every saved exchange.' },
  { icon: BookOpenIcon, title: 'A knowledge base per agent', text: 'Store text, find it by meaning with vector search, import and export it as plain JSON. Every agent has its own.' },
  { icon: PlugIcon, title: 'MCP tools', text: 'Attach external tool servers to an agent. A server that goes down is left out for a while instead of breaking the answer.' },
  { icon: GitBranchIcon, title: 'Versions and rollback', text: 'Every change to a prompt, a model, the settings or the tools is a numbered version. Compare any two, and go back with one click.' },
  { icon: FileAudioIcon, title: 'Files and voice', text: 'Pass images, PDFs and audio to models that understand them. Record a voice message right in the playground and send it as a WAV file.' },
  { icon: KeyRoundIcon, title: 'Tokens with roles', text: 'Regular, user, admin and owner. Each token is bound to an agent, and only its hash is stored. The secret is shown once, when it is made.' },
  { icon: ChartColumnIcon, title: 'Usage per token', text: 'See requests, tokens, cost and response time for every token on charts. Never the texts. Old usage is folded into monthly totals that stay.' },
  { icon: ShieldCheckIcon, title: 'Built to keep running', text: 'Failed provider calls are retried, a client that left stops the work, and every request is a JSON log line with the secrets masked, plus Prometheus metrics.' },
]

const STEPS = [
  { n: '1', title: 'Make an agent', text: 'Give it a name, a prompt and a model. Add tools, a knowledge base and MCP servers when you need them.' },
  { n: '2', title: 'Make a token', text: 'Pick a role and the agent it opens. Copy the secret: it is shown once.' },
  { n: '3', title: 'Call the API', text: 'Send messages for your users. Watch the usage, roll back a prompt, change the model, all without redeploying.' },
]

const STACK = ['FastAPI', 'PostgreSQL', 'pgvector', 'OpenRouter', 'MCP', 'pydantic-ai', 'Prometheus', 'React', 'Server-sent events', 'Docker']

const SNIPPET = `from omnixon import Client

client = Client(token="<your token>", base_url="https://omnixon.net")

answer = await client.send_message("telegram-42", "Remind me what we decided about pricing?")
print(answer.response)

async for chunk in client.send_message_stream("telegram-42", "And the plan after that?"):
    print(chunk, end="")`

const CURL = `curl https://omnixon.net/api/v1/request \\
  -H "Authorization: Bearer <your token>" \\
  -H "Content-Type: application/json" \\
  -d '{"user_id": "telegram-42",
       "request": "Remind me what we decided about pricing?"}'`

// the answer of POST /request: the text is what matters, the rest is dust
const RESPONSE = `{
  "response": "You said the team plan stays at $20 a seat, and the free tier gets 100 requests a month. I also remember you prefer yearly billing.",
  ...
}`

export default function Landing() {
  const { resolvedTheme, setTheme } = useTheme()
  const dark = resolvedTheme !== 'light'
  // one flat colour for the dots (no gradient), and a faint glow under the cursor
  const dots = dark ? 'rgba(250, 250, 250, 0.28)' : 'rgba(24, 24, 27, 0.28)'
  const glow = dark ? 'rgba(250, 250, 250, 0.06)' : 'rgba(24, 24, 27, 0.05)'
  return (
    <div className="min-h-svh bg-background text-foreground">
      <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/80 px-4 backdrop-blur md:px-6">
        {/* the way in is the first thing at the left */}
        <Button variant="outline" size="sm" nativeButton={false} render={<Link to="/login" />}>
          <KeyRoundIcon /> Login
        </Button>
        <Link to="/" className="flex items-center gap-2 font-medium" aria-label="Omnixon">
          <Logo className="size-6" /> Omnixon
        </Link>
        <nav className="ml-auto flex items-center gap-1 text-sm text-muted-foreground" aria-label="Sections">
          <a href="#features" className="hidden rounded-md px-2 py-1 hover:text-foreground sm:block">
            Features
          </a>
          <a href="#how" className="hidden rounded-md px-2 py-1 hover:text-foreground sm:block">
            How it works
          </a>
          <a href="#code" className="hidden rounded-md px-2 py-1 hover:text-foreground sm:block">
            Code
          </a>
          <Button variant="ghost" size="icon-sm" aria-label="Toggle theme" onClick={() => setTheme(dark ? 'light' : 'dark')}>
            {dark ? <SunIcon /> : <MoonIcon />}
          </Button>
        </nav>
      </header>

      <main>
        {/* the first screen: the hero and the strip of what it is built with under it, together as high as the window below the header */}
        <div className="flex min-h-[calc(100svh-3.5rem)] flex-col">
        <section className="relative isolate flex flex-1 flex-col overflow-hidden">
          <div aria-hidden className="absolute inset-0 -z-10">
            <DotField dotRadius={1.6} dotSpacing={16} cursorRadius={420} bulgeStrength={60} gradientFrom={dots} gradientTo={dots} glowColor={glow} />
          </div>
          <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 pb-10 md:px-6">
            <h1 className="sr-only">Omnixon</h1>
            {/* the name and the tagline sit in the middle of what is left above the example: equal room above and below */}
            <div className="flex flex-1 flex-col justify-center py-8">
            <div className="relative h-[30svh] min-h-52" aria-hidden>
              <TechText key={dark ? 'dark' : 'light'} text="Omnixon" color={dark ? '#fafafa' : '#18181b'} accentColor={dark ? '#7c8cff' : '#4f46e5'} fontWeight={700} reach={220} labels selection />
            </div>
            <div className="text-center">
              <p className="mx-auto min-h-8 max-w-2xl text-balance text-xl text-muted-foreground md:text-2xl">
                <TextType
                  text={['Give your bot a memory.', 'Give your site an assistant.', 'Give every model the same interface.']}
                  typingSpeed={45}
                  deletingSpeed={25}
                  pauseDuration={1800}
                  cursorCharacter="_"
                />
              </p>
            </div>
            </div>

            {/* a request, and what comes back: the whole idea at a glance */}
            <AnimatedContent distance={40} duration={0.8} threshold={0.05}>
              <div className="grid gap-4 text-left lg:grid-cols-2" aria-label="A request and its answer">
                <div className="rounded-xl border bg-card/80 p-1 backdrop-blur">
                  <CodeBlock code={CURL} lang="bash" className="my-0 border-0 bg-transparent" />
                </div>
                <div className="rounded-xl border bg-card/80 p-1 backdrop-blur" data-testid="hero-chat">
                  <CodeBlock code={RESPONSE} lang="json" className="my-0 border-0 bg-transparent [&_code]:whitespace-pre-wrap [&_code]:break-words [&_pre]:whitespace-pre-wrap" />
                </div>
              </div>
            </AnimatedContent>
          </div>
        </section>

        <section className="border-y bg-muted/30 py-5" aria-label="Built with">
          <LogoLoop
            logos={STACK.map((name) => ({ node: <span className="px-2 text-sm font-medium text-muted-foreground">{name}</span>, title: name }))}
            speed={50}
            gap={36}
            logoHeight={24}
            fadeOut
            fadeOutColor={dark ? '#0a0a0a' : '#fafafa'}
            ariaLabel="Built with"
          />
        </section>
        </div>

        <section id="features" className="mx-auto max-w-6xl px-4 py-24 md:px-6">
          <div className="mb-12 text-center">
            <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">
              <BlurText text="Everything between your client and the model" animateBy="words" delay={90} className="justify-center" />
            </h2>
            <p className="mx-auto mt-3 max-w-2xl text-muted-foreground">Omnixon builds the context for every request, calls the model, stores the exchange and returns the answer, so your clients only have to ask.</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f, i) => (
              <AnimatedContent key={f.title} distance={40} duration={0.7} delay={(i % 3) * 0.08} threshold={0.15}>
                <SpotlightCard className="h-full rounded-xl !border-border !bg-card !p-5" spotlightColor="rgba(160, 160, 170, 0.14)">
                  <f.icon className="mb-3 size-5 text-muted-foreground" />
                  <h3 className="font-medium">{f.title}</h3>
                  <p className="mt-1.5 text-sm text-muted-foreground">{f.text}</p>
                </SpotlightCard>
              </AnimatedContent>
            ))}
          </div>
        </section>

        <section className="border-y bg-muted/30 py-16" aria-label="In numbers">
          <div className="mx-auto grid max-w-5xl gap-8 px-4 text-center sm:grid-cols-3 md:px-6">
            {[
              { to: 4, label: 'roles, from a plain client to the owner' },
              { to: 2, label: 'ways to answer: JSON and a live stream' },
              { to: 100, suffix: '%', label: 'of what a model costs, counted per token' },
            ].map((s) => (
              <div key={s.label}>
                <div className="text-5xl font-semibold tabular-nums">
                  <CountUp to={s.to} duration={1.6} />
                  {s.suffix}
                </div>
                <p className="mt-2 text-sm text-muted-foreground">{s.label}</p>
              </div>
            ))}
          </div>
        </section>

        <section id="how" className="mx-auto max-w-5xl px-4 py-24 md:px-6">
          <h2 className="mb-12 text-center text-3xl font-semibold tracking-tight md:text-4xl">From nothing to answers in three steps</h2>
          <ol className="grid gap-4 md:grid-cols-3">
            {STEPS.map((s, i) => (
              <AnimatedContent key={s.n} distance={30} duration={0.6} delay={i * 0.1} threshold={0.2}>
                <li className="h-full rounded-xl border bg-card p-6">
                  <span className="grid size-8 place-items-center rounded-full border bg-muted font-mono text-sm">{s.n}</span>
                  <h3 className="mt-4 font-medium">{s.title}</h3>
                  <p className="mt-1.5 text-sm text-muted-foreground">{s.text}</p>
                </li>
              </AnimatedContent>
            ))}
          </ol>
        </section>

        <section id="code" className="mx-auto max-w-4xl px-4 pb-24 md:px-6">
          <h2 className="mb-6 text-center text-3xl font-semibold tracking-tight">A client in a few lines</h2>
          <Tabs defaultValue="python">
            <TabsList className="mb-2">
              <TabsTrigger value="python">Python</TabsTrigger>
              <TabsTrigger value="curl">curl</TabsTrigger>
            </TabsList>
            <TabsContent value="python">
              <CodeBlock code={SNIPPET} lang="python" className="my-0" />
            </TabsContent>
            <TabsContent value="curl">
              <CodeBlock code={CURL} lang="bash" className="my-0" />
            </TabsContent>
          </Tabs>
          <p className="mt-3 text-center text-sm text-muted-foreground">
            The Python library is <code className="value-mono">omnixon-lib</code>. Every endpoint is also documented at <code className="value-mono">/docs</code> on the service.
          </p>
        </section>

        <section id="connections" className="mx-auto max-w-6xl px-4 pb-24 md:px-6" aria-label="Channels, agents and models">
          <div className="mb-14 text-center">
            <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Many channels, one brain, any model</h2>
            <p className="mx-auto mt-3 max-w-2xl text-muted-foreground">
              Telegram, WhatsApp, Discord, Avito or your own site all talk to the same Omnixon. It gives each user their history and memory, hands the message to the right agent, and the agent runs on whichever model you choose, even your own server.
            </p>
          </div>
          <AnimatedContent distance={40} duration={0.8} threshold={0.1}>
            <ConnectionsGraph />
          </AnimatedContent>
        </section>

        <section className="relative isolate overflow-hidden border-t py-24 text-center">
          <div aria-hidden className="absolute inset-0 -z-10">
            <DotField dotRadius={1.4} dotSpacing={18} cursorRadius={360} bulgeStrength={50} gradientFrom={dots} gradientTo={dots} glowColor={glow} />
          </div>
          <h2 className="mx-auto max-w-2xl text-balance text-3xl font-semibold tracking-tight md:text-4xl">Ready to see it work?</h2>
          <p className="mx-auto mt-3 max-w-xl text-muted-foreground">Sign in with a token and try an agent in the playground, with text, files or your voice.</p>
          <div className="mt-8">
            <Button size="lg" nativeButton={false} render={<Link to="/login" />}>
              <KeyRoundIcon /> Login
            </Button>
          </div>
        </section>
      </main>

      <footer className="border-t px-4 py-6 text-center text-sm text-muted-foreground md:px-6">
        <a href="https://omnixon.net" className="font-medium underline-offset-4 hover:underline hover:text-foreground">omnixon.net</a>: one API for every model, memory and tool.
      </footer>
    </div>
  )
}
