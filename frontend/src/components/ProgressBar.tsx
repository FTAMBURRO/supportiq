import styles from './ProgressBar.module.css'

export type BarTone = 'blue' | 'amber' | 'green' | 'red' | 'gray'

/** Horizontal bar for dashboard overviews. Pure CSS, no chart library.
 * The numeric value is always visible as text next to the bar; `tone`
 * only tints the fill and never replaces the label. */
export default function ProgressBar({
  label,
  value,
  max,
  tone,
}: {
  label: string
  value: number
  max: number
  tone?: BarTone
}) {
  const width = max > 0 ? Math.round((value / max) * 100) : 0
  const fillClass = tone ? `${styles.fill} ${styles[tone]}` : styles.fill
  return (
    <div className={styles.row}>
      <span className={styles.label}>{label}</span>
      <div
        className={styles.track}
        role="img"
        aria-label={`${label}: ${value}`}
      >
        <div className={fillClass} style={{ width: `${width}%` }} />
      </div>
      <span className={styles.value}>{value}</span>
    </div>
  )
}
