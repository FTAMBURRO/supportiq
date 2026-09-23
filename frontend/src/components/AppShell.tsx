import { LayoutDashboard, Plus, Ticket as TicketIcon } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import styles from './AppShell.module.css'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/tickets', label: 'Tickets', icon: TicketIcon, end: false },
  { to: '/tickets/new', label: 'Create Ticket', icon: Plus, end: false },
]

/** Application shell: fixed sidebar + main content area (desktop-first;
 * the sidebar collapses to a top bar on narrow viewports). */
export default function AppShell() {
  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>
          <span className={styles.logo}>SupportIQ</span>
          <span className={styles.demoBadge}>Demo</span>
        </div>
        <nav className={styles.nav} aria-label="Main navigation">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `${styles.navLink} ${isActive ? styles.navLinkActive : ''}`
              }
            >
              <Icon size={16} aria-hidden="true" />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}
