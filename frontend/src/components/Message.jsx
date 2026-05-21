import ReactMarkdown from 'react-markdown'
import { Scale, User, BookOpen } from 'lucide-react'
import styles from './Message.module.css'

export default function Message({ role, content, sources, index }) {
  const isBot = role === 'assistant'
  return (
    <div
      className={`${styles.wrapper} ${isBot ? styles.bot : styles.user} fade-up`}
      style={{ animationDelay: `${Math.min(index * 0.05, 0.3)}s` }}
    >
      <div className={styles.avatar}>
        {isBot ? <Scale size={15} /> : <User size={15} />}
      </div>

      <div className={styles.bubble}>
        <div className={styles.content}>
          {isBot
            ? <ReactMarkdown>{content}</ReactMarkdown>
            : <p>{content}</p>
          }
        </div>

        {isBot && sources && sources.length > 0 && (
          <div className={styles.sources}>
            <div className={styles.sourcesLabel}>
              <BookOpen size={11} />
              Источники
            </div>
            <div className={styles.sourceList}>
              {sources.map((s, i) => (
                <span key={i} className={styles.source}>
                  {s.source}
                  {s.article !== '—' && ` · ст. ${s.article}`}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
