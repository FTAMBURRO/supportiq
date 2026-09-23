import { AlertCircle, Loader2 } from 'lucide-react'
import styles from './States.module.css'

/** The three states every async screen needs: loading, API error, empty. */

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className={styles.loading} role="status">
      <Loader2 size={18} className={styles.spinner} aria-hidden="true" />
      {label}
    </div>
  )
}

export function ErrorBanner({
  message,
  onRetry,
}: {
  message: string
  onRetry?: () => void
}) {
  return (
    <div className={styles.error} role="alert">
      <AlertCircle size={16} aria-hidden="true" />
      <span>{message}</span>
      {onRetry && (
        <button type="button" className={styles.retry} onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  )
}

export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string
  hint?: string
  action?: React.ReactNode
}) {
  return (
    <div className={styles.empty}>
      <p className={styles.emptyTitle}>{title}</p>
      {hint && <p className={styles.emptyHint}>{hint}</p>}
      {action}
    </div>
  )
}
