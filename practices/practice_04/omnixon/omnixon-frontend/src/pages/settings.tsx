import { useState } from 'react'
import { useTheme } from 'next-themes'
import { EyeIcon, EyeOffIcon, LogOutIcon } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { FieldGroup, FieldSeparator } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from '@/components/ui/input-group'
import { CopyButton } from '@/components/display'
import { MonitorIcon, MoonIcon, SunIcon } from 'lucide-react'
import { FormField, OptionSelect } from '@/components/form'
import { Page, PageHeader, PageScroll } from '@/components/page'
import { session } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { maskToken } from '@/lib/format'

export default function SettingsPage() {
  const { token, logout } = useAuth()
  const { theme, setTheme } = useTheme()
  const [base, setBase] = useState(session.baseUrl)
  const [reveal, setReveal] = useState(false)

  return (
    <Page>
      <PageHeader title="Settings" description="Connection and appearance. Stored in this browser only." />
      <PageScroll className="grid content-start gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Connection</CardTitle>
            <CardDescription>Token “{token?.name}” ({token?.role}) is signed in.</CardDescription>
          </CardHeader>
          <CardContent>
            <FieldGroup>
              <FormField label="Token">
                <InputGroup>
                  <InputGroupInput readOnly className="value-mono" value={reveal ? session.token : maskToken(session.token)} />
                  <InputGroupAddon align="inline-end">
                    <InputGroupButton size="icon-xs" aria-label={reveal ? 'Hide token' : 'Show token'} onClick={() => setReveal((v) => !v)}>
                      {reveal ? <EyeOffIcon /> : <EyeIcon />}
                    </InputGroupButton>
                    <CopyButton text={session.token} label="Copy token" />
                  </InputGroupAddon>
                </InputGroup>
              </FormField>
              <FieldSeparator />
              <FormField label="API URL" description="Empty = same origin (the /api proxy). A direct URL requires CORS on the service.">
                <Input value={base} onChange={(e) => setBase(e.target.value)} placeholder="http://localhost:8083" />
              </FormField>
            </FieldGroup>
          </CardContent>
          <CardFooter className="justify-between">
            <Button variant="destructive" onClick={logout}>
              <LogOutIcon /> Sign out
            </Button>
            <Button
              onClick={() => {
                session.baseUrl = base
                toast.success('API URL saved, reloading…')
                setTimeout(() => location.reload(), 600)
              }}
            >
              Save
            </Button>
          </CardFooter>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Appearance</CardTitle>
            <CardDescription>The theme follows your system unless you choose one.</CardDescription>
          </CardHeader>
          <CardContent>
            <FieldGroup>
              <FormField label="Theme">
                <OptionSelect
                  value={theme ?? 'system'}
                  onChange={setTheme}
                  options={[
                    { value: 'system', label: 'System', icon: MonitorIcon, description: 'Follow the theme of your device' },
                    { value: 'light', label: 'Light', icon: SunIcon, description: 'Light surfaces, dark text' },
                    { value: 'dark', label: 'Dark', icon: MoonIcon, description: 'Dark surfaces, light text' },
                  ]}
                />
              </FormField>
            </FieldGroup>
          </CardContent>
        </Card>
      </PageScroll>
    </Page>
  )
}
