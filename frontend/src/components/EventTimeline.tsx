import { formatDateTime } from '../utils/format'
import { actorLabel, formatEvent, type EventNameMaps } from '../utils/formatEvent'
import type { TicketEvent } from '../types'
import styles from './EventTimeline.module.css'

/** Ticket history: one friendly row per event, oldest first. Never raw
 * JSON; ids are resolved to names through the reference maps. */
export default function EventTimeline({
  events,
  maps,
}: {
  events: TicketEvent[]
  maps: EventNameMaps
}) {
  return (
    <ol className={styles.timeline}>
      {events.map((event) => {
        const { text, detail } = formatEvent(event, maps)
        return (
          <li key={event.id} className={styles.item}>
            <span className={styles.time}>{formatDateTime(event.created_at)}</span>
            <div className={styles.body}>
              <span className={styles.text}>{text}</span>
              {detail && <span className={styles.detail}>{detail}</span>}
              <span className={styles.actor}>{actorLabel(event)}</span>
            </div>
          </li>
        )
      })}
    </ol>
  )
}
