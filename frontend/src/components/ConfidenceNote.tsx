import { HelpCircle } from 'lucide-react'
import { formatConfidence } from '../utils/format'
import styles from './ConfidenceNote.module.css'

/** Responsible presentation of the classifier score: a "confidence
 * score", explicitly not a probability, with the honest explanation. */
export default function ConfidenceNote({ value }: { value: number }) {
  return (
    <div className={styles.wrap}>
      <span className={styles.score}>Confidence score: {formatConfidence(value)}</span>
      <span className={styles.explain}>
        <HelpCircle size={13} aria-hidden="true" />
        Based on similarity and agreement with historical tickets.
      </span>
    </div>
  )
}
