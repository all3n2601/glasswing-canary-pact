"use client";

import { ContactShadows, OrbitControls, useGLTF } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { Suspense, useEffect, useMemo, useRef } from "react";
import type { Group, Object3D } from "three";
import { CanvasTexture, LinearFilter, MathUtils, Mesh, SRGBColorSpace, Vector3 } from "three";

import type { DepartmentImpactTone, DepartmentSimulationView } from "@/lib/simulation-view";

export type DepartmentSceneMarker = Pick<DepartmentSimulationView, "departmentId" | "name" | "label" | "tone" | "position" | "strength" | "startsAt">;

interface AgentRoute {
  id: string;
  start: [number, number, number];
  end: [number, number, number];
  finalRotation: number;
  stagger: number;
}

const agentRoutes: AgentRoute[] = [
  { id: "finance", start: [-6.05, 0.13, -5.5], end: [0, 0.13, -2.4], finalRotation: 0, stagger: 0 },
  { id: "engineering", start: [1.55, 0.13, -5.5], end: [2.08, 0.13, -1.2], finalRotation: -Math.PI / 3, stagger: 1 },
  { id: "product", start: [9.15, 0.13, -5.5], end: [2.08, 0.13, 1.2], finalRotation: -2 * Math.PI / 3, stagger: 2 },
  { id: "customer_success", start: [9.15, 0.13, 5.8], end: [0, 0.13, 2.4], finalRotation: Math.PI, stagger: 3 },
  { id: "sales", start: [1.55, 0.13, 5.8], end: [-2.08, 0.13, 1.2], finalRotation: 2 * Math.PI / 3, stagger: 4 },
  { id: "operations", start: [-6.05, 0.13, 5.8], end: [-2.08, 0.13, -1.2], finalRotation: Math.PI / 3, stagger: 5 },
];

const tones: Record<DepartmentImpactTone, string> = {
  source: "#4f7fa7",
  positive: "#4ca27c",
  negative: "#df6d63",
  neutral: "#71717a",
};

function enableShadows(object: Object3D) {
  object.traverse((child) => {
    if (child instanceof Mesh) {
      child.castShadow = true;
      child.receiveShadow = true;
    }
  });
}

function setPartPose(agent: Object3D, id: string, seated: number, gait: number) {
  // The source is authored seated: pelvis rests on the cushion, hips and shoulders
  // are joint pivots, and shoes/hands stay attached through knee/elbow chains.
  agent.position.y = MathUtils.lerp(0.43, 0, seated);
  for (const [side, sign] of [["left", 1], ["right", -1]] as const) {
    const leg = agent.getObjectByName(`${id}_${side}_leg`);
    const shin = agent.getObjectByName(`${id}_${side}_shin`);
    const shoe = agent.getObjectByName(`${id}_${side}_shoe`);
    const arm = agent.getObjectByName(`${id}_${side}_arm`);
    const forearm = agent.getObjectByName(`${id}_${side}_forearm`);
    const hipAngle = MathUtils.lerp(gait * sign, -Math.PI / 2, seated);
    const kneeAngle = MathUtils.lerp(Math.max(0, -gait * sign) * 0.65, Math.PI / 2, seated);
    if (leg) leg.rotation.x = hipAngle;
    if (shin) shin.rotation.x = kneeAngle;
    if (shoe) shoe.rotation.x = -(hipAngle + kneeAngle);
    if (arm) arm.rotation.x = MathUtils.lerp(-gait * sign * 0.55, -0.95, seated);
    if (forearm) forearm.rotation.x = MathUtils.lerp(-0.12, -0.75, seated);
  }
}

function AnimatedAgent({ source, route, day }: { source: Object3D; route: AgentRoute; day: number }) {
  const root = useRef<Group>(null);
  const agent = useMemo(() => {
    const copy = source.clone(true);
    copy.position.set(0, 0, 0);
    copy.rotation.set(0, 0, 0);
    enableShadows(copy);
    return copy;
  }, [source]);
  const start = useMemo(() => new Vector3(...route.start), [route.start]);
  const end = useMemo(() => new Vector3(...route.end), [route.end]);

  useFrame(({ clock }) => {
    if (!root.current) return;
    const localDay = day < 0 ? -1 : day - route.stagger;
    const move = localDay < 0 ? 0 : MathUtils.smoothstep(localDay, 8, 27);
    const meetingSit = localDay < 0 ? 0 : MathUtils.smoothstep(localDay, 27, 34);
    const initialSit = localDay < 0 ? 1 : 1 - MathUtils.smoothstep(localDay, 2, 8);
    const seated = Math.max(initialSit, meetingSit);
    const walking = localDay > 8 && localDay < 28;
    const gait = walking ? Math.sin(clock.elapsedTime * 9 + route.stagger) * 0.65 : 0;

    root.current.position.lerpVectors(start, end, move);
    if (walking) {
      root.current.rotation.y = Math.atan2(end.x - start.x, end.z - start.z);
      root.current.position.y = route.start[1] + Math.abs(Math.sin(clock.elapsedTime * 9 + route.stagger)) * 0.04;
    } else {
      root.current.rotation.y = move >= 0.99 ? route.finalRotation : Math.PI;
    }
    setPartPose(agent, route.id, seated, gait);
  });

  return <group ref={root}><primitive object={agent} /></group>;
}

function PulseField({ impact, day, selected, showAllLabels, onSelect }: { impact: DepartmentSceneMarker; day: number; selected: boolean; showAllLabels: boolean; onSelect?: (departmentId: string) => void }) {
  const pulseGroup = useRef<Group>(null);
  const disc = useRef<Mesh>(null);
  const visible = day >= impact.startsAt;
  const labelVisible = showAllLabels || selected || day >= impact.startsAt + 5;
  const visibleLabel = day < 0 ? "View department" : impact.label;
  const progress = MathUtils.clamp((day - impact.startsAt) / 20, 0, 1);
  const labelTexture = useMemo(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 768;
    canvas.height = 192;
    const context = canvas.getContext("2d");

    if (context) {
      context.scale(2, 2);
      context.fillStyle = selected ? "rgba(24, 24, 27, 0.97)" : "rgba(255, 255, 255, 0.96)";
      context.beginPath();
      context.roundRect(1, 1, 382, 94, 22);
      context.fill();
      context.strokeStyle = selected ? "rgba(24, 24, 27, 1)" : "rgba(255, 255, 255, 0.98)";
      context.lineWidth = 2;
      context.stroke();

      context.fillStyle = tones[impact.tone];
      context.beginPath();
      context.arc(28, 48, 8, 0, Math.PI * 2);
      context.fill();

      context.fillStyle = selected ? "#ffffff" : "#18181b";
      context.font = "600 20px system-ui, sans-serif";
      context.fillText(impact.name, 52, 41);
      context.fillStyle = selected ? "#d4d4d8" : "#71717a";
      context.font = "400 16px system-ui, sans-serif";
      context.fillText(visibleLabel, 52, 67);
    }

    const texture = new CanvasTexture(canvas);
    texture.colorSpace = SRGBColorSpace;
    texture.minFilter = LinearFilter;
    texture.generateMipmaps = false;
    return texture;
  }, [impact, selected, visibleLabel]);

  useEffect(() => () => labelTexture.dispose(), [labelTexture]);

  useFrame(({ clock }) => {
    if (!pulseGroup.current || !disc.current) return;
    const pulse = 1 + Math.sin(clock.elapsedTime * 1.25) * 0.035;
    const scale = MathUtils.lerp(pulseGroup.current.scale.x, visible || selected ? pulse : 0.01, 0.08);
    pulseGroup.current.scale.setScalar(scale);
    const material = disc.current.material;
    if (!Array.isArray(material)) material.opacity = MathUtils.lerp(material.opacity, visible ? 0.1 + impact.strength * 0.09 * progress : 0, 0.08);
  });

  return (
    <group position={impact.position}>
      <group ref={pulseGroup} scale={0.01}>
        <mesh ref={disc} rotation={[-Math.PI / 2, 0, 0]} renderOrder={4}>
          <circleGeometry args={[3.15 + impact.strength * 1.15, 64]} />
          <meshBasicMaterial color={tones[impact.tone]} transparent opacity={0} depthWrite={false} />
        </mesh>
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.012, 0]} renderOrder={5}>
          <ringGeometry args={[2.2 + impact.strength, 2.25 + impact.strength, 64]} />
          <meshBasicMaterial color={tones[impact.tone]} transparent opacity={visible || selected ? 0.5 : 0} depthWrite={false} />
        </mesh>
      </group>
      <sprite
        position={[0, 1.25, 0]}
        scale={[3.8, 0.95, 1]}
        visible={labelVisible}
        renderOrder={20}
        onClick={(event) => { event.stopPropagation(); onSelect?.(impact.departmentId); }}
        onPointerOver={() => { if (onSelect) document.body.style.cursor = "pointer"; }}
        onPointerOut={() => { document.body.style.cursor = ""; }}
      >
        <spriteMaterial map={labelTexture} transparent depthTest={false} depthWrite={false} />
      </sprite>
    </group>
  );
}

function OfficeWorld({ day }: { day: number }) {
  const { scene } = useGLTF("/assets/3d/office.glb");
  const office = useMemo(() => {
    const copy = scene.clone(true);
    agentRoutes.forEach(({ id }) => {
      const originalAgent = copy.getObjectByName(`agent_${id}`);
      if (originalAgent) originalAgent.visible = false;
    });
    enableShadows(copy);
    return copy;
  }, [scene]);

  return (
    <>
      <primitive object={office} />
      {agentRoutes.map((route) => {
        const source = scene.getObjectByName(`agent_${route.id}`);
        return source ? <AnimatedAgent key={route.id} source={source} route={route} day={day} /> : null;
      })}
    </>
  );
}

function Scene({ day, interactive, departments, selectedDepartmentId, showAllDepartmentLabels, onDepartmentSelect }: { day: number; interactive: boolean; departments: DepartmentSceneMarker[]; selectedDepartmentId?: string; showAllDepartmentLabels: boolean; onDepartmentSelect?: (departmentId: string) => void }) {
  return (
    <>
      <ambientLight intensity={1.15} />
      <hemisphereLight color="#fffdf7" groundColor="#cbd5d1" intensity={0.8} />
      <directionalLight position={[10, 18, 8]} intensity={1.75} castShadow shadow-mapSize-width={2048} shadow-mapSize-height={2048} shadow-bias={-0.0003} />
      <OfficeWorld day={day} />
      {departments.map((impact) => <PulseField key={impact.departmentId} impact={impact} day={day} selected={selectedDepartmentId === impact.departmentId} showAllLabels={showAllDepartmentLabels} onSelect={onDepartmentSelect} />)}
      <ContactShadows position={[0, -0.21, 0]} opacity={0.18} scale={34} blur={2.8} far={12} />
      {interactive ? <OrbitControls makeDefault enablePan={false} minPolarAngle={0.62} maxPolarAngle={1.12} minDistance={18} maxDistance={35} target={[0, 0, 0]} /> : null}
    </>
  );
}

export function OfficeScene({ day, interactive = true, departments = [], selectedDepartmentId, showAllDepartmentLabels = false, onDepartmentSelect }: { day: number; interactive?: boolean; departments?: DepartmentSceneMarker[]; selectedDepartmentId?: string; showAllDepartmentLabels?: boolean; onDepartmentSelect?: (departmentId: string) => void }) {
  return (
    <Canvas camera={{ position: [19, 20, 24], fov: 38 }} dpr={[1, 1.6]} gl={{ antialias: true, alpha: true }} shadows>
      <Suspense fallback={null}><Scene day={day} interactive={interactive} departments={departments} selectedDepartmentId={selectedDepartmentId} showAllDepartmentLabels={showAllDepartmentLabels} onDepartmentSelect={onDepartmentSelect} /></Suspense>
    </Canvas>
  );
}

useGLTF.preload("/assets/3d/office.glb");
