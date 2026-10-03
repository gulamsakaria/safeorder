import { useEffect, useRef } from 'react'

const DUST_COUNT = 500
const BIT_COUNT = 26
const WIDE_BREAKPOINT = 900
const PALETTE = [0x6366f1, 0x22d3ee, 0xa855f7, 0xf472b6]

function webglAvailable(): boolean {
  try {
    return !!document.createElement('canvas').getContext('webgl2')
  } catch {
    return false
  }
}

/**
 * Decorative animated 3D background (a shield-like core, rings and floating shapes).
 * It never takes part in any decision: it is loaded lazily, ignores the pointer for
 * clicks, and quietly does nothing where WebGL is missing (older phones, the test runner).
 */
export function Scene3D() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !webglAvailable()) return
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
    let stop = () => {}
    let cancelled = false

    void import('three').then((T) => {
      if (cancelled) return
      const renderer = new T.WebGLRenderer({ canvas, alpha: true, antialias: true })
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
      const scene = new T.Scene()
      const camera = new T.PerspectiveCamera(55, 1, 0.1, 100)
      camera.position.z = 9

      scene.add(new T.AmbientLight(0x8890ff, 1.6))
      const cyan = new T.PointLight(0x22d3ee, 60, 0, 1)
      cyan.position.set(6, 5, 6)
      const violet = new T.PointLight(0xa855f7, 60, 0, 1)
      violet.position.set(-6, -4, 5)
      scene.add(cyan, violet)

      const disposables: { dispose(): void }[] = []
      const track = <D extends { dispose(): void }>(d: D) => {
        disposables.push(d)
        return d
      }

      // hero: glowing core, wireframe shell and two rings
      const hero = new T.Group()
      const core = new T.Mesh(
        track(new T.IcosahedronGeometry(1.5, 1)),
        track(new T.MeshStandardMaterial({ color: 0x6366f1, metalness: 0.7, roughness: 0.25, flatShading: true, emissive: 0x2a2f9e, emissiveIntensity: 0.7 })),
      )
      const shell = new T.Mesh(
        track(new T.IcosahedronGeometry(2.2, 1)),
        track(new T.MeshBasicMaterial({ color: 0x67e8f9, wireframe: true, transparent: true, opacity: 0.35 })),
      )
      const ringGeo = track(new T.TorusGeometry(3, 0.03, 12, 120))
      const ringMat = track(new T.MeshBasicMaterial({ color: 0xa5b4fc, transparent: true, opacity: 0.7 }))
      const ring1 = new T.Mesh(ringGeo, ringMat)
      const ring2 = new T.Mesh(ringGeo, ringMat)
      ring2.rotation.x = Math.PI / 2.4
      ring2.scale.setScalar(1.15)
      hero.add(core, shell, ring1, ring2)
      scene.add(hero)

      // floating shapes
      const shapes = [
        track(new T.BoxGeometry(0.5, 0.5, 0.5)),
        track(new T.OctahedronGeometry(0.42)),
        track(new T.TetrahedronGeometry(0.45)),
      ]
      const bits: { mesh: InstanceType<typeof T.Mesh>; speed: number; phase: number; y: number }[] = []
      for (let i = 0; i < BIT_COUNT; i++) {
        const mat = track(new T.MeshStandardMaterial({ color: PALETTE[i % PALETTE.length], metalness: 0.6, roughness: 0.3, transparent: true, opacity: 0.75 }))
        const mesh = new T.Mesh(shapes[i % shapes.length], mat)
        const angle = Math.random() * Math.PI * 2
        const radius = 5 + Math.random() * 6
        mesh.position.set(Math.cos(angle) * radius, (Math.random() - 0.5) * 10, -Math.random() * 8 + Math.sin(angle) * 2)
        mesh.scale.setScalar(0.5 + Math.random() * 1.1)
        scene.add(mesh)
        bits.push({ mesh, speed: 0.004 + Math.random() * 0.01, phase: Math.random() * 6, y: mesh.position.y })
      }

      // star dust
      const positions = new Float32Array(DUST_COUNT * 3)
      for (let i = 0; i < positions.length; i++) positions[i] = (Math.random() - 0.5) * 40
      const dustGeo = track(new T.BufferGeometry())
      dustGeo.setAttribute('position', new T.BufferAttribute(positions, 3))
      const dust = new T.Points(dustGeo, track(new T.PointsMaterial({ color: 0xc7d2fe, size: 0.05, transparent: true, opacity: 0.8 })))
      scene.add(dust)

      let px = 0
      let py = 0
      let tx = 0
      let ty = 0
      const resize = () => {
        const w = window.innerWidth
        const h = window.innerHeight
        renderer.setSize(w, h, false)
        camera.aspect = w / h
        camera.updateProjectionMatrix()
        const narrow = w < WIDE_BREAKPOINT
        // wide screens: beside the content column; phones: below the header, behind empty space
        hero.position.set(narrow ? 0 : 5.2, narrow ? -3.6 : 0.4, 0)
        hero.scale.setScalar(narrow ? 0.6 : 1)
      }
      const onMove = (e: PointerEvent) => {
        tx = e.clientX / window.innerWidth - 0.5
        ty = e.clientY / window.innerHeight - 0.5
      }
      window.addEventListener('resize', resize)
      window.addEventListener('pointermove', onMove, { passive: true })
      resize()

      const t0 = performance.now()
      let raf = 0
      let running = !document.hidden
      const frame = () => {
        const t = (performance.now() - t0) / 1000
        px += (tx - px) * 0.05
        py += (ty - py) * 0.05
        hero.rotation.y = t * 0.35 + px * 1.2
        hero.rotation.x = Math.sin(t * 0.4) * 0.2 + py * 0.8
        ring1.rotation.z = t * 0.5
        ring2.rotation.y = -t * 0.4
        shell.rotation.y = -t * 0.2
        core.scale.setScalar(1 + Math.sin(t * 1.6) * 0.04)
        for (const b of bits) {
          b.mesh.rotation.x += b.speed * 2
          b.mesh.rotation.y += b.speed * 3
          b.mesh.position.y = b.y + Math.sin(t * 0.6 + b.phase) * 0.6
        }
        dust.rotation.y = t * 0.02
        camera.position.x += (px * 1.5 - camera.position.x) * 0.04
        camera.position.y += (-py - camera.position.y) * 0.04
        camera.lookAt(0, 0, 0)
        renderer.render(scene, camera)
        if (running && !reduce) raf = requestAnimationFrame(frame)
      }
      const onVisibility = () => {
        running = !document.hidden
        if (running && !reduce) raf = requestAnimationFrame(frame)
      }
      document.addEventListener('visibilitychange', onVisibility)
      frame()

      stop = () => {
        cancelAnimationFrame(raf)
        window.removeEventListener('resize', resize)
        window.removeEventListener('pointermove', onMove)
        document.removeEventListener('visibilitychange', onVisibility)
        disposables.forEach((d) => d.dispose())
        renderer.dispose()
      }
    })

    return () => {
      cancelled = true
      stop()
    }
  }, [])

  return <canvas ref={canvasRef} aria-hidden="true" className="so-scene" />
}
