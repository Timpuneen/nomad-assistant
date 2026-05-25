import { useState, useEffect, useRef } from 'react'
import {
  listLaws, toggleLaw,
  listUploads, uploadDocument, deleteUpload,
  getStats,
} from '../api/client'
import {
  Scale, Upload, FileText, Trash2, Plus,
  Loader, BarChart2, BookMarked, FolderOpen,
  Eye, EyeOff,
} from 'lucide-react'
import styles from './Sidebar.module.css'

export default function Sidebar({ onNewChat }) {
  const [laws,     setLaws]     = useState([])   // [{filename, enabled}]
  const [uploads,  setUploads]  = useState([])   // [string]
  const [stats,    setStats]    = useState(null)
  const [uploading,setUploading]= useState(false)
  const [uploadMsg,setUploadMsg]= useState(null)
  const [toggling, setToggling] = useState(null) // filename being toggled
  const [deleting, setDeleting] = useState(null) // filename being deleted
  const fileRef = useRef()

  const load = async () => {
    try {
      const [l, u, s] = await Promise.all([listLaws(), listUploads(), getStats()])
      setLaws(l.laws   || [])
      setUploads(u.uploads || [])
      setStats(s)
    } catch {}
  }

  useEffect(() => { load() }, [])

  // ── Upload handler ────────────────────────────────────────────────────────

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setUploadMsg(null)
    try {
      const res = await uploadDocument(file)
      setUploadMsg({ ok: true, text: `Добавлено ${res.chunks_indexed} фрагментов` })
      await load()
      // Auto-hide success message after 3 seconds
      setTimeout(() => setUploadMsg(null), 3000)
    } catch {
      setUploadMsg({ ok: false, text: 'Ошибка загрузки' })
      // Auto-hide error message after 5 seconds
      setTimeout(() => setUploadMsg(null), 5000)
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  // ── Toggle law ────────────────────────────────────────────────────────────

  const handleToggle = async (filename, currentEnabled) => {
    setToggling(filename)
    try {
      await toggleLaw(filename, !currentEnabled)
      setLaws(prev => prev.map(l =>
        l.filename === filename ? { ...l, enabled: !currentEnabled } : l
      ))
    } catch {}
    finally { setToggling(null) }
  }

  // ── Delete upload ─────────────────────────────────────────────────────────

  const handleDelete = async (filename) => {
    setDeleting(filename)
    try {
      await deleteUpload(filename)
      await load()
    } finally { setDeleting(null) }
  }

  return (
    <aside className={styles.sidebar}>
      {/* Logo */}
      <div className={styles.logo}>
        <Scale size={22} className={styles.logoIcon} />
        <div>
          <div className={styles.logoTitle}>Insurance Assistant</div>
          <div className={styles.logoSub}>Законы РК · Страхование</div>
        </div>
      </div>

      {/* New chat */}
      <button className={styles.newChat} onClick={onNewChat}>
        <Plus size={15} />
        Новый диалог
      </button>

      {/* ── Laws section ── */}
      <div className={styles.section}>
        <div className={styles.sectionLabel}>
          <BookMarked size={13} />
          База законов
          <span className={styles.badge}>{laws.length}</span>
        </div>

        {laws.length === 0 ? (
          <div className={styles.empty}>
            <FileText size={24} opacity={0.2} />
            <span>Законы не загружены.<br/>Положите .docx в папку laws/</span>
          </div>
        ) : (
          laws.map(({ filename, enabled }) => (
            <div
              key={filename}
              className={`${styles.docItem} ${!enabled ? styles.disabled : ''}`}
            >
              <FileText size={13} className={styles.docIcon} />
              <span className={styles.docName} title={filename}>{filename}</span>
              <button
                className={`${styles.iconBtn} ${enabled ? styles.eyeOn : styles.eyeOff}`}
                onClick={() => handleToggle(filename, enabled)}
                disabled={toggling === filename}
                title={enabled ? 'Отключить' : 'Включить'}
              >
                {toggling === filename
                  ? <Loader size={13} className={styles.spin} />
                  : enabled ? <Eye size={13} /> : <EyeOff size={13} />
                }
              </button>
            </div>
          ))
        )}
      </div>

      {/* ── Uploads section ── */}
      <div className={styles.section}>
        <div className={styles.sectionLabel}>
          <FolderOpen size={13} />
          Мои документы
          <span className={styles.badge}>{uploads.length}</span>
        </div>

        <button
          className={styles.uploadBtn}
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
        >
          {uploading
            ? <><Loader size={14} className={styles.spin} /> Индексирую…</>
            : <><Upload size={14} /> Загрузить документ (.docx)</>
          }
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".docx"
          style={{ display: 'none' }}
          onChange={handleUpload}
        />

        {uploadMsg && (
          <div className={`${styles.uploadMsg} ${uploadMsg.ok ? styles.ok : styles.err}`}>
            {uploadMsg.text}
          </div>
        )}

        {uploads.length > 0 && (
          <div className={styles.uploadList}>
            {uploads.map(name => (
              <div key={name} className={styles.docItem}>
                <FileText size={13} className={styles.docIcon} />
                <span className={styles.docName} title={name}>{name}</span>
                <button
                  className={`${styles.iconBtn} ${styles.deleteBtn}`}
                  onClick={() => handleDelete(name)}
                  disabled={deleting === name}
                  title="Удалить"
                >
                  {deleting === name
                    ? <Loader size={13} className={styles.spin} />
                    : <Trash2 size={13} />
                  }
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Stats */}
      {stats && (
        <div className={styles.stats}>
          <BarChart2 size={13} />
          <span>
            {stats.total_laws} зак. · {stats.total_uploads} докум. · {stats.total_chunks} фрагм.
          </span>
        </div>
      )}
    </aside>
  )
}
