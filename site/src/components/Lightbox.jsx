import { createContext, useCallback, useContext, useEffect, useState } from 'react'

const Ctx = createContext(() => {})
export const useLightbox = () => useContext(Ctx)

export function LightboxProvider({ children }) {
  const [item, setItem] = useState(null)
  const open = useCallback((src, caption) => setItem({ src, caption }), [])
  useEffect(() => {
    if (!item) return
    const onKey = (e) => e.key === 'Escape' && setItem(null)
    window.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [item])
  return (
    <Ctx.Provider value={open}>
      {children}
      {item && (
        <div className="lightbox" role="dialog" aria-modal="true" aria-label={item.caption} onClick={() => setItem(null)}>
          <figure onClick={(e) => e.stopPropagation()}>
            <img src={item.src} alt={item.caption} />
            {item.caption && <figcaption>{item.caption}</figcaption>}
          </figure>
          <button className="lightbox-close" aria-label="Close" onClick={() => setItem(null)}>×</button>
        </div>
      )}
    </Ctx.Provider>
  )
}

export function Figure({ src, caption, className = '' }) {
  const open = useLightbox()
  return (
    <figure className={`fig ${className}`}>
      <button className="fig-btn" onClick={() => open(src, caption)} aria-label={`Enlarge: ${caption}`}>
        <img src={src} alt={caption} loading="lazy" />
      </button>
      {caption && <figcaption>{caption}</figcaption>}
    </figure>
  )
}
