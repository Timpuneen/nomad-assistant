import { useState, useCallback } from 'react'
import Sidebar from './components/Sidebar'
import Chat from './pages/Chat'
import styles from './App.module.css'

let sessionCounter = 0
const newSessionId = () => `session-${++sessionCounter}-${Date.now()}`

export default function App() {
  const [sessionId, setSessionId] = useState(newSessionId())
  const [resetKey, setResetKey] = useState(0)

  const handleNewChat = useCallback(() => {
    setSessionId(newSessionId())
    setResetKey(k => k + 1)
  }, [])

  return (
    <div className={styles.app}>
      <Sidebar onNewChat={handleNewChat} />
      <Chat sessionId={sessionId} resetKey={resetKey} />
    </div>
  )
}
