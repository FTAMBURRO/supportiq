import styles from './StatCard.module.css'

/** Dashboard headline number. */
export default function StatCard({
  label,
  value,
}: {
  label: string
  value: number
}) {
  return (
    <div className={styles.card}>
      <span className={styles.value}>{value}</span>
      <span className={styles.label}>{label}</span>
    </div>
  )
}
