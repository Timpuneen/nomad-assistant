import { useState, useEffect, useRef } from 'react'
import { uploadDocument, listDocuments, deleteDocument, getStats } from '../api/client'
import {
  Scale, Upload, FileText, Trash2, ChevronRight,
  Database, BarChart2, Plus, Loader,
} from 'lucide-react'
import styles from './Sidebar.module.css'

export default function Sidebar({ onNewChat }) {
  const [docs, setDocs] = useState([])
  const [stats, setStats] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadMsg, setUploadMsg] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const fileRef = useRef()

  const load = async () => {
    try {
      const [d, s] = await Promise.all([listDocuments(), getStats()])
      setDocs(d.documents || [])
      setStats(s)
    } catch {}
  }

  useEffect(() => { load() }, [])

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setUploadMsg(null)
    try {
      const res = await uploadDocument(file)
      setUploadMsg({ ok: true, text: `Добавлено ${res.chunks_indexed} фрагментов` })
      await load()
    } catch (err) {
      setUploadMsg({ ok: false, text: 'Ошибка загрузки' })
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const handleDelete = async (name) => {
    setDeleting(name)
    try {
      await deleteDocument(name)
      await load()
    } finally {
      setDeleting(null)
    }
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

      {/* Upload */}
      <div className={styles.section}>
        <div className={styles.sectionLabel}>
          <Database size={13} />
          База знаний
        </div>

        <button
          className={styles.uploadBtn}
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
        >
          {uploading
            ? <><Loader size={14} className={styles.spin} /> Индексирую…</>
            : <><Upload size={14} /> Загрузить закон (.docx)</>
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
      </div>

      {/* Document list */}
      <div className={styles.docList}>
        {docs.length === 0 ? (
          <div className={styles.empty}>
            <FileText size={28} opacity={0.2} />
            <span>Документы не загружены</span>
          </div>
        ) : (
          docs.map((doc) => (
            <div key={doc} className={styles.docItem}>
              <FileText size={13} className={styles.docIcon} />
              <span className={styles.docName} title={doc}>{doc}</span>
              <button
                className={styles.deleteBtn}
                onClick={() => handleDelete(doc)}
                disabled={deleting === doc}
                title="Удалить"
              >
                {deleting === doc
                  ? <Loader size={12} className={styles.spin} />
                  : <Trash2 size={12} />
                }
              </button>
            </div>
          ))
        )}
      </div>

      {/* Stats */}
      {stats && (
        <div className={styles.stats}>
          <BarChart2 size={13} />
          <span>{stats.total_documents} докум. · {stats.total_chunks} фрагм.</span>
        </div>
      )}
    </aside>
  )
}
