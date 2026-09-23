import { userName } from '../api/reference'
import type { PaginatedTickets, UserSummary } from '../types'
import { formatRelativeTime } from '../utils/format'
import { CategoryBadge, PriorityBadge, StatusBadge } from './Badges'
import styles from './TicketTable.module.css'

/** Ticket rows: real columns only, backend order (newest first), no
 * sorting UI because the API does not support sorting. The row links to
 * the detail page; the ticket-number anchor keeps it keyboard
 * accessible. */
export default function TicketTable({
  page,
  users,
  onOpen,
}: {
  page: PaginatedTickets
  users: UserSummary[]
  onOpen: (ticketNumber: string) => void
}) {
  return (
    <div className={styles.wrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">Ticket</th>
            <th scope="col">Title</th>
            <th scope="col">Status</th>
            <th scope="col">Priority</th>
            <th scope="col">Category</th>
            <th scope="col">Requester</th>
            <th scope="col">Created</th>
          </tr>
        </thead>
        <tbody>
          {page.items.map((ticket) => (
            <tr
              key={ticket.id}
              className={styles.row}
              onClick={() => onOpen(ticket.ticket_number)}
            >
              <td>
                <a
                  className={styles.number}
                  href={`/tickets/${ticket.ticket_number}`}
                  onClick={(event) => {
                    event.preventDefault()
                    event.stopPropagation()
                    onOpen(ticket.ticket_number)
                  }}
                >
                  {ticket.ticket_number}
                </a>
              </td>
              <td className={styles.title}>{ticket.title}</td>
              <td>
                <StatusBadge status={ticket.status} />
              </td>
              <td>
                <PriorityBadge priority={ticket.priority} />
              </td>
              <td>
                {ticket.category ? (
                  <CategoryBadge name={ticket.category.name} />
                ) : (
                  <span className={styles.none}>—</span>
                )}
              </td>
              <td className={styles.requester}>
                {userName(users, ticket.requester_id)}
              </td>
              <td className={styles.created}>
                {formatRelativeTime(ticket.created_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
