import { useState } from 'react'
import { simVideo } from '../data.js'

const base = import.meta.env.BASE_URL

export default function SimVideo() {
  const [failed, setFailed] = useState(false)
  if (simVideo.youtube) {
    return (
      <div className="video">
        <iframe
          src={`https://www.youtube-nocookie.com/embed/${simVideo.youtube}`}
          title="Simulation video"
          allow="accelerometer; encrypted-media; picture-in-picture; fullscreen"
          allowFullScreen
        />
      </div>
    )
  }
  if (simVideo.src && !failed) {
    return (
      <div className="video">
        <video controls preload="metadata" playsInline poster={base + simVideo.poster} onError={() => setFailed(true)}>
          <source src={base + simVideo.src} type="video/mp4" onError={() => setFailed(true)} />
        </video>
      </div>
    )
  }
  return (
    <div className="video placeholder" style={{ backgroundImage: `url(${base + simVideo.poster})` }}>
      <div className="video-msg">
        <span className="play" aria-hidden="true">▶</span>
        <b>Simulation video coming soon</b>
        <span>A recording of the robot mapping the campus and delivering a multi-stop order.</span>
      </div>
    </div>
  )
}
