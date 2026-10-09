import { useState } from 'react'
import { useTheme } from 'next-themes'
import { EyeIcon, EyeOffIcon, LanguagesIcon, LogOutIcon } from 'lucide-react'
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
import { locale, switchLocale, t, type Locale } from '@/lib/i18n'
import { roleName } from '@/lib/roles'

export default function SettingsPage() {
  const { token, logout } = useAuth()
  const { theme, setTheme } = useTheme()
  const [base, setBase] = useState(session.baseUrl)
  const [reveal, setReveal] = useState(false)

  return (
    <Page>
      <PageHeader title={t('Settings')} description={t('Connection and appearance. Stored in this browser only.')} />
      <PageScroll className="grid content-start gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t('Connection')}</CardTitle>
            <CardDescription>{t('Token “{name}” ({role}) is signed in.', { name: token?.name ?? '', role: token ? roleName(token.role) : '' })}</CardDescription>
          </CardHeader>
          <CardContent>
            <FieldGroup>
              <FormField label={t('Token')}>
                <InputGroup>
                  <InputGroupInput readOnly className="value-mono" value={reveal ? session.token : maskToken(session.token)} />
                  <InputGroupAddon align="inline-end">
                    <InputGroupButton size="icon-xs" aria-label={reveal ? t('Hide token') : t('Show token')} onClick={() => setReveal((v) => !v)}>
                      {reveal ? <EyeOffIcon /> : <EyeIcon />}
                    </InputGroupButton>
                    <CopyButton text={session.token} label={t('Copy token')} />
                  </InputGroupAddon>
                </InputGroup>
              </FormField>
              <FieldSeparator />
              <FormField label={t('API URL')} description={t('Empty = same origin (the /api proxy). A direct URL requires CORS on the service.')}>
                <Input value={base} onChange={(e) => setBase(e.target.value)} placeholder="http://localhost:8083" />
              </FormField>
            </FieldGroup>
          </CardContent>
          <CardFooter className="justify-between">
            <Button variant="destructive" onClick={logout}>
              <LogOutIcon /> {t('Sign out')}
            </Button>
            <Button
              onClick={() => {
                session.baseUrl = base
                toast.success(t('API URL saved, reloading…'))
                setTimeout(() => location.reload(), 600)
              }}
            >
              {t('Save')}
            </Button>
          </CardFooter>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t('Appearance')}</CardTitle>
            <CardDescription>{t('The theme follows your system unless you choose one.')}</CardDescription>
          </CardHeader>
          <CardContent>
            <FieldGroup>
              <FormField label={t('Language')} description={t('The panel opens in this language on every visit; it is kept in this browser.')}>
                <OptionSelect
                  value={locale}
                  onChange={(v) => v !== locale && switchLocale(v as Locale)}
                  options={[
                    { value: 'en', label: 'English', icon: LanguagesIcon, description: t('The panel in English') },
                    { value: 'ru', label: 'Русский', icon: LanguagesIcon, description: t('The panel in Russian') },
                  ]}
                />
              </FormField>
              <FieldSeparator />
              <FormField label={t('Theme')}>
                <OptionSelect
                  value={theme ?? 'system'}
                  onChange={setTheme}
                  options={[
                    { value: 'system', label: t('System'), icon: MonitorIcon, description: t('Follow the theme of your device') },
                    { value: 'light', label: t('Light'), icon: SunIcon, description: t('Light surfaces, dark text') },
                    { value: 'dark', label: t('Dark'), icon: MoonIcon, description: t('Dark surfaces, light text') },
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
