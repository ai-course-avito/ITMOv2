import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AppRoutes, Providers } from '../App'

export function renderApp(path = '/') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Providers>
        <AppRoutes />
      </Providers>
    </MemoryRouter>,
  )
}
