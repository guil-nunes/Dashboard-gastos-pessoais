import { NavLink, Outlet } from 'react-router-dom'
import HealthIndicator from './HealthIndicator.tsx'

const NAV_ITEMS = [
  { to: '/importar', label: 'Importar' },
  { to: '/revisar', label: 'Revisar' },
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/recorrentes', label: 'Recorrentes' },
  { to: '/parcelas', label: 'Parcelas' },
]

export default function Layout() {
  return (
    <div className="layout">
      <header className="layout-header">
        <nav className="layout-nav">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} to={item.to}>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <HealthIndicator />
      </header>
      <main className="layout-main">
        <Outlet />
      </main>
    </div>
  )
}
