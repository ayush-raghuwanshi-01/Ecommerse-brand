import { useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Environment, Lightformer, Sparkles } from "@react-three/drei";
import * as THREE from "three";
import { colors } from "../../theme";

export interface HeroCanvasProps {
  /** When true nothing rotates, drifts or parallaxes. */
  reducedMotion: boolean;
}

interface GoldKnotProps {
  reducedMotion: boolean;
}

/**
 * The hero object: a metallic antique-gold torus knot, lit by point lights and
 * an in-scene environment map so the metal has something to reflect.
 *
 * Motion is paused when the visitor prefers reduced motion or when the tab is
 * backgrounded; the parallax lerp still settles back to centre in that case.
 */
function GoldKnot({ reducedMotion }: GoldKnotProps) {
  const group = useRef<THREE.Group>(null);

  useFrame((state, delta) => {
    const node = group.current;
    if (!node) return;

    const tabHidden =
      typeof document !== "undefined" && document.visibilityState === "hidden";
    const animate = !reducedMotion && !tabHidden;

    // Clamp delta so a long backgrounded frame cannot jump the rotation.
    const step = Math.min(delta, 0.05);
    if (animate) {
      node.rotation.x += step * 0.15;
      node.rotation.y += step * 0.21;
    }

    const targetX = animate ? state.pointer.x * 0.55 : 0;
    const targetY = animate ? -state.pointer.y * 0.34 : 0;
    node.position.x = THREE.MathUtils.lerp(node.position.x, targetX, 0.05);
    node.position.y = THREE.MathUtils.lerp(node.position.y, targetY, 0.05);
  });

  return (
    <group ref={group}>
      <mesh>
        <torusKnotGeometry args={[1.15, 0.34, 240, 32]} />
        <meshStandardMaterial
          color={colors.gold}
          metalness={1}
          roughness={0.22}
          emissive={colors.goldDeep}
          emissiveIntensity={0.38}
          envMapIntensity={1.2}
        />
      </mesh>

      {/* A hairline ring behind the knot, to give the composition some depth. */}
      <mesh rotation={[Math.PI / 2.35, 0, 0.2]}>
        <torusGeometry args={[2.5, 0.005, 6, 200]} />
        <meshBasicMaterial color={colors.gold} transparent opacity={0.2} />
      </mesh>
    </group>
  );
}

export default function HeroCanvas({ reducedMotion }: HeroCanvasProps) {
  return (
    <Canvas
      // alpha:true so the page's near-black background shows straight through.
      gl={{ alpha: true, antialias: true, powerPreference: "high-performance" }}
      camera={{ position: [0, 0, 6.4], fov: 40 }}
      dpr={[1, 1.75]}
      style={{ position: "absolute", inset: 0 }}
    >
      <ambientLight intensity={0.45} color="#f2e7d2" />
      <pointLight
        position={[5, 4, 6]}
        intensity={130}
        distance={30}
        decay={2}
        color={colors.goldBright}
      />
      <pointLight
        position={[-6, -3.5, -5]}
        intensity={60}
        distance={32}
        decay={2}
        color="#8fa6b8"
      />

      <GoldKnot reducedMotion={reducedMotion} />

      {/* Slow gold dust. Speed goes to zero under prefers-reduced-motion. */}
      <Sparkles
        count={70}
        scale={[12, 8, 5]}
        size={1.8}
        speed={reducedMotion ? 0 : 0.22}
        opacity={0.42}
        color={colors.goldBright}
      />

      {/*
        Procedural environment map — built in-scene, so there is no HDR file to
        download. This is what actually makes the metal read as metal.
      */}
      <Environment resolution={256} frames={1}>
        <Lightformer
          form="rect"
          intensity={2.6}
          color="#f6e3bb"
          position={[0, 4, 5]}
          scale={[9, 3, 1]}
        />
        <Lightformer
          form="rect"
          intensity={0.7}
          color="#8fa6b8"
          position={[-6, -2, -4]}
          scale={[8, 4, 1]}
        />
        <Lightformer
          form="circle"
          intensity={1.4}
          color="#fff6e4"
          position={[5, -3, 3]}
          scale={4}
        />
      </Environment>
    </Canvas>
  );
}
