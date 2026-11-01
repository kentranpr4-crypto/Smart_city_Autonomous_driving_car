// WP0 TOOLCHAIN SMOKE ONLY. This is not the city, not a VIS deliverable, and shows no backend state.
// It proves: React 19 + R3F 9 + three build and can create a WebGL context. Real scene arrives in WP6.
import React from 'react'
import { createRoot } from 'react-dom/client'
import { Canvas, useFrame } from '@react-three/fiber'

function Box() {
  const ref = React.useRef()
  useFrame((_, dt) => { ref.current.rotation.y += dt })       // smoke animation only
  return (
    <mesh ref={ref} castShadow>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial color="#4fa3ff" />
    </mesh>
  )
}

function onCreated({ gl }) {
  const ctx = gl.getContext()
  const ext = ctx.getExtension('WEBGL_debug_renderer_info')
  window.__smoke = {
    webgl2: typeof WebGL2RenderingContext !== 'undefined' && ctx instanceof WebGL2RenderingContext,
    renderer: ext ? ctx.getParameter(ext.UNMASKED_RENDERER_WEBGL) : ctx.getParameter(ctx.RENDERER),
    vendor: ext ? ctx.getParameter(ext.UNMASKED_VENDOR_WEBGL) : ctx.getParameter(ctx.VENDOR),
    maxTexture: ctx.getParameter(ctx.MAX_TEXTURE_SIZE),
  }
}

createRoot(document.getElementById('root')).render(
  <Canvas shadows camera={{ position: [2.5, 2, 3.5], fov: 45 }} onCreated={onCreated}>
    <color attach="background" args={['#0e1420']} />
    <ambientLight intensity={0.6} />
    <directionalLight position={[4, 6, 3]} intensity={1.6} castShadow />
    <Box />
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.8, 0]} receiveShadow>
      <planeGeometry args={[10, 10]} />
      <shadowMaterial opacity={0.35} />
    </mesh>
  </Canvas>,
)
