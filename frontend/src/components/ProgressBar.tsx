import styles from './ProgressBar.module.css'

/** Horizontal bar for dashboard overviews. Pure CSS, no chart library.
 * The numeric value is always visible as text next to the bar. */
export default function ProgressBar({
  label,
  value,
  max,
}: {
  label: string
  value: number
  max: number
}) {
  const width = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div className={styles.row}>
      <span className={styles.label}>{label}</span>
      <div
        className={styles.track}
        role="img"
        aria-label={`${label}: ${value}`}
      >
        <div className={styles.fill} style={{ width: `${width}%` }} />
      </div>
      <span className={styles.value}>{value}</span>
    </div>
  )
}
