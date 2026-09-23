import { Route, Routes } from 'react-router-dom'
import AppShell from './components/AppShell'
import CreateTicketPage from './pages/CreateTicketPage'
import DashboardPage from './pages/DashboardPage'
import TicketDetailPage from './pages/TicketDetailPage'
import TicketsPage from './pages/TicketsPage'
import styles from './pages/NotFound.module.css'

function NotFoundPage() {
  return (
    <div className={styles.wrap}>
      <h1>Page not found</h1>
      <p className={styles.hint}>
        The page you are looking for does not exist.{' '}
        <a href="/">Back to the dashboard</a>
      </p>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/tickets" element={<TicketsPage />} />
        <Route path="/tickets/new" element={<CreateTicketPage />} />
        <Route path="/tickets/:ticketNumber" element={<TicketDetailPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
