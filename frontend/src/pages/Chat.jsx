import { useState, useRef, useEffect, useCallback } from 'react'
import { sendMessage } from '../api/client'
import Message from '../components/Message'
import { Send, Loader, Scale } from 'lucide-react'
import styles from './Chat.module.css'

const SUGGESTIONS = [
  'Что такое договор страхования по ГК РК?',
  'Какие формы страхования предусмотрены законодательством?',
  'Что такое система «бонус-малус»?',
  'Кто является выгодоприобретателем по ОСАГО?',
  'Что признаётся страховым случаем?',
  'Чем отличается обязательное страхование от добровольного?',
]

export default function Chat({ sessionId, resetKey }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef()
  const inputRef = useRef()

  useEffect(() => {
    setMessages([])
    setInput('')
    inputRef.current?.focus()
  }, [resetKey])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const submit = useCallback(async (text) => {
    const q = (text || input).trim()
    if (!q || loading) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: q }])
    setLoading(true)
    try {
      const res = await sendMessage(q, sessionId)
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: res.answer, sources: res.sources },
      ])
    } catch {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: '⚠️ Ошибка соединения с сервером. Проверьте, что бэкенд запущен.', sources: [] },
      ])
    } finally {
      setLoading(false)
    }
  }, [input, loading, sessionId])

  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() }
  }

  const isEmpty = messages.length === 0

  return (
    <div className={styles.chat}>
      {/* Messages area */}
      <div className={styles.messages}>
        {isEmpty && (
          <div className={styles.welcome + ' fade-up'}>
            <div className={styles.welcomeIcon}>
              <Scale size={36} />
            </div>
            <h1 className={styles.welcomeTitle}>Insurance Assistant</h1>
            <p className={styles.welcomeSub}>
              Задайте вопрос по страховому законодательству Республики Казахстан
            </p>
            <div className={styles.suggestions}>
              {SUGGESTIONS.map((s, i) => (
                <button
                  key={i}
                  className={styles.suggestion}
                  style={{ animationDelay: `${0.1 + i * 0.06}s` }}
                  onClick={() => submit(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <Message
            key={i}
            index={i}
            role={msg.role}
            content={msg.content}
            sources={msg.sources}
          />
        ))}

        {loading && (
          <div className={styles.thinking + ' fade-in'}>
            <div className={styles.thinkingAvatar}>
              <Scale size={15} />
            </div>
            <div className={styles.thinkingDots}>
              <span /><span /><span />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className={styles.inputBar}>
        <div className={styles.inputWrap}>
          <textarea
            ref={inputRef}
            className={styles.input}
            placeholder="Введите вопрос по страховому законодательству РК…"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={onKey}
            rows={1}
            disabled={loading}
          />
          <button
            className={styles.send}
            onClick={() => submit()}
            disabled={!input.trim() || loading}
          >
            {loading
              ? <Loader size={18} className={styles.spin} />
              : <Send size={18} />
            }
          </button>
        </div>
        <div className={styles.hint}>Enter — отправить · Shift+Enter — новая строка</div>
      </div>
    </div>
  )
}
