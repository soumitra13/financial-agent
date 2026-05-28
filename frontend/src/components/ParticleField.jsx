import { useEffect, useRef } from 'react'

export default function ParticleField({ opacity = 0.7 }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    let animId
    let particles = []

    const resize = () => {
      canvas.width  = canvas.offsetWidth
      canvas.height = canvas.offsetHeight
    }
    resize()
    window.addEventListener('resize', resize)

    const COUNT = Math.floor((canvas.width * canvas.height) / 14000)

    for (let i = 0; i < COUNT; i++) {
      particles.push({
        x:  Math.random() * canvas.width,
        y:  Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        r:  Math.random() * 1.5 + 0.5,
        alpha: Math.random() * 0.6 + 0.2,
        pulse: Math.random() * Math.PI * 2,
      })
    }

    const LINK_DIST = 130
    const CYAN  = [0, 212, 255]
    const PURP  = [139, 92, 246]

    function draw() {
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      particles.forEach(p => {
        p.x += p.vx
        p.y += p.vy
        p.pulse += 0.012
        if (p.x < 0) p.x = canvas.width
        if (p.x > canvas.width) p.x = 0
        if (p.y < 0) p.y = canvas.height
        if (p.y > canvas.height) p.y = 0
      })

      // Draw connections
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x
          const dy = particles[i].y - particles[j].y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist < LINK_DIST) {
            const a = (1 - dist / LINK_DIST) * 0.18
            const mix = i % 3 === 0 ? PURP : CYAN
            ctx.strokeStyle = `rgba(${mix[0]},${mix[1]},${mix[2]},${a})`
            ctx.lineWidth = 0.6
            ctx.beginPath()
            ctx.moveTo(particles[i].x, particles[i].y)
            ctx.lineTo(particles[j].x, particles[j].y)
            ctx.stroke()
          }
        }
      }

      // Draw particles
      particles.forEach((p, i) => {
        const pulsed = p.alpha * (0.7 + 0.3 * Math.sin(p.pulse))
        const c = i % 4 === 0 ? PURP : CYAN
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(${c[0]},${c[1]},${c[2]},${pulsed})`
        ctx.fill()
      })

      animId = requestAnimationFrame(draw)
    }

    draw()
    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', resize)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        opacity,
        pointerEvents: 'none',
      }}
    />
  )
}
