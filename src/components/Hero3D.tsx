import { Suspense, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Environment } from '@react-three/drei';
import type { Mesh } from 'three';

function Knot() {
  const ref = useRef<Mesh>(null);
  useFrame(({ clock, mouse }) => {
    if (!ref.current) return;
    ref.current.rotation.y = clock.elapsedTime * 0.22;
    ref.current.rotation.x = clock.elapsedTime * 0.12;
    ref.current.position.x += (mouse.x * 0.45 - ref.current.position.x) * 0.03;
    ref.current.position.y += (mouse.y * 0.25 - ref.current.position.y) * 0.03;
  });
  return (
    <mesh ref={ref}>
      <torusKnotGeometry args={[1.45, 0.42, 180, 32]} />
      <meshStandardMaterial color="#c9a24b" metalness={0.9} roughness={0.18} />
    </mesh>
  );
}

export default function Hero3D() {
  return (
    <Canvas className="hero-canvas" camera={{ position: [0, 0, 5], fov: 45 }} gl={{ alpha: true }}>
      <ambientLight intensity={0.35} />
      <pointLight position={[3, 3, 4]} intensity={18} color="#e8c873" />
      <pointLight position={[-4, -2, 2]} intensity={10} color="#8a5e24" />
      <Suspense fallback={null}>
        <Knot />
        <Environment preset="city" />
      </Suspense>
    </Canvas>
  );
}
