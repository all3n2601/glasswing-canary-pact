"use client";

import { ContactShadows, Line, OrbitControls, RoundedBox, useGLTF, useProgress } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Component, Suspense, useEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from "react";
import { Group, Mesh, MeshStandardMaterial, Vector3 } from "three";
import { DeskFurniture, MeetingTable, OfficeChair, OfficeEnvironment } from "./office-furnishings";
import { officePosition } from "@/lib/office-layout";
import type { DepartmentSimulationView } from "@/lib/simulation-view";

export type DepartmentSceneMarker = Pick<DepartmentSimulationView, "departmentId" | "name" | "label" | "tone" | "position" | "strength" | "startsAt">;
export interface OfficeParticipant { key: string; name: string; status: "analyzing" | "available" | "unavailable"; selected?: boolean }
const tones = { source: "#729bc0", positive: "#56a78a", negative: "#df776c", neutral: "#90a79f" };

class SceneBoundary extends Component<{children: ReactNode}, {failed: boolean}> {
  state = {failed: false};
  static getDerivedStateFromError() { return {failed: true}; }
  render() { return this.state.failed ? <div role="alert" className="absolute inset-0 grid place-content-center gap-3 text-center text-sm text-zinc-600"><p>The office could not load. The department list and dependency map remain available.</p><button className="mx-auto rounded-xl border bg-white px-4 py-2" onClick={()=>{useGLTF.clear("/assets/3d/office.glb");this.setState({failed:false});}}>Retry office</button></div> : this.props.children; }
}

/** Project label anchors into the ordinary DOM; avoid a separate React root per label. */
function LabelAnchor({position, element}: {position: [number,number,number]; element: () => HTMLDivElement | undefined}) {
  const anchor = useRef<Group>(null);
  const point = useMemo(()=>new Vector3(),[]);
  useFrame(({camera,size}) => {
    const label = element();
    if (!label || !anchor.current) return;
    anchor.current.getWorldPosition(point).project(camera);
    label.style.visibility = point.z < -1 || point.z > 1 ? "hidden" : "visible";
    label.style.transform = `translate(${(point.x+1)*size.width/2}px,${(1-point.y)*size.height/2}px) translate(-50%,-50%)`;
  });
  return <group ref={anchor} position={position} />;
}

const wardrobe = ["#577c80", "#bb9164", "#677596", "#8b797d", "#6a8264", "#406371"];
function characterSeed(identity: string) {
  return [...identity].reduce((value, letter) => (value * 31 + letter.charCodeAt(0)) >>> 0, 7);
}

function Representative({position, active, reducedMotion, identity}: {position: [number, number, number]; active: boolean; reducedMotion: boolean; identity: string}) {
  const root = useRef<Group>(null);
  const {scene} = useGLTF("/assets/3d/office.glb");
  const seed = characterSeed(identity);
  const model = useMemo(() => {
    const source = scene.getObjectByName("agent_finance");
    if (!source) return null;
    const agent = source.clone(true);
    agent.position.set(0,0,0);agent.rotation.set(0,0,0);
    const materials: MeshStandardMaterial[] = [];
    agent.traverse(node=>{
      if (node instanceof Mesh && /finance_(body|.*sleeve)$/.test(node.name) && node.material instanceof MeshStandardMaterial) {
        node.material = node.material.clone();
        node.material.color.set(wardrobe[seed % wardrobe.length]);
        materials.push(node.material);
      }
    });
    const head = new Group();head.position.set(0,1.3,0);agent.add(head);agent.updateMatrixWorld(true);
    for (const name of ["head","hair","nose","neck"]) {
      const part = agent.getObjectByName(`finance_${name}`);
      if (part) head.attach(part);
    }
    for (const side of ["left", "right"]) {
      const arm = agent.getObjectByName(`finance_${side}_arm`);
      if (arm) arm.rotation.x = -0.35;
    }
    return {agent,head,materials,left:agent.getObjectByName("finance_left_forearm"),right:agent.getObjectByName("finance_right_forearm")};
  }, [scene,seed]);
  useEffect(()=>()=>model?.materials.forEach(material=>material.dispose()),[model]);
  useFrame(({clock}) => {
    if (!model) return;
    const time = clock.elapsedTime + seed % 37;
    // Idle glances are ambience; typing and screen pulses require an actual analyzing event.
    model.head.rotation.y = reducedMotion ? 0 : Math.sin(time*0.45)*0.13;
    model.head.rotation.x = reducedMotion ? 0 : Math.sin(time*0.7)*0.035;
    if (root.current) root.current.rotation.y = reducedMotion ? 0 : Math.sin(time*0.32)*0.025;
    const motion = reducedMotion ? 0 : active ? 0.12 : 0.015;
    if (model.left) model.left.rotation.x = -1.15 + Math.sin(time*(active?7:0.8))*motion;
    if (model.right) model.right.rotation.x = -1.15 + Math.cos(time*(active?7:0.8))*motion;
  });
  return <group ref={root} position={position}>{model ? <primitive object={model.agent} /> : <mesh><capsuleGeometry args={[0.2,0.5]}/><meshStandardMaterial color="#465f62"/></mesh>}</group>;
}

function CameraFocus({target, resetKey, board, wide, reducedMotion}: {target?: [number, number, number]; resetKey: number; board: boolean; wide: boolean; reducedMotion: boolean}) {
  const {camera, controls, size} = useThree();
  const destination = useRef<{position: Vector3; center: Vector3} | null>(null);
  const orbit = controls as unknown as {target: Vector3; update: () => void; addEventListener: (name: string, listener: () => void) => void; removeEventListener: (name: string, listener: () => void) => void} | undefined;
  useEffect(() => {
    const center = target ? new Vector3(...target) : new Vector3(0,0,0);
    const offset = new Vector3(...(target ? [8,9,11] : board ? [8,9,11] : wide ? [34,37,43] : [25,27,32]) as [number,number,number]);
    if (!target) offset.multiplyScalar(Math.max(1,Math.min(1.8,size.height/Math.max(size.width,1))));
    destination.current = {position:center.clone().add(offset),center};
    if (reducedMotion) {
      camera.position.copy(destination.current.position);camera.lookAt(center);
      if (orbit) {orbit.target.copy(center);orbit.update();}
      destination.current=null;
    }
    const interrupt=()=>{destination.current=null;};
    orbit?.addEventListener("start",interrupt);
    return ()=>orbit?.removeEventListener("start",interrupt);
  }, [camera,controls,target?.[0],target?.[1],target?.[2],resetKey,board,wide,size.width,size.height,reducedMotion]);
  useFrame((_,delta)=>{
    const goal=destination.current;
    if (!goal || !orbit) return;
    const ease=1-Math.exp(-delta*6);
    camera.position.lerp(goal.position,ease);orbit.target.lerp(goal.center,ease);orbit.update();
    if (camera.position.distanceToSquared(goal.position)<0.0001 && orbit.target.distanceToSquared(goal.center)<0.0001) destination.current=null;
  });
  return null;
}

function Workstation({department, day, active, selected, onSelect, reducedMotion, labels}: {labels: RefObject<Map<string, HTMLDivElement>>; department: DepartmentSceneMarker; day: number; active: boolean; selected: boolean; onSelect?: (id: string) => void; reducedMotion: boolean}) {
  const closed = department.label.startsWith("Closed") && day >= department.startsAt;
  const color = day >= department.startsAt ? tones[department.tone] : tones.neutral;
  const accent = wardrobe[characterSeed(department.departmentId) % wardrobe.length];
  const [hovered,setHovered] = useState(false);
  return <group position={department.position} onPointerOver={event=>{event.stopPropagation();setHovered(true);}} onPointerOut={()=>setHovered(false)} onClick={e=>{e.stopPropagation();onSelect?.(department.departmentId);}}>
    <RoundedBox args={[4.2, 0.12, 3.7]} radius={0.04} position={[0, -0.03, 0]} onClick={e => {e.stopPropagation(); onSelect?.(department.departmentId);}}>
      <meshStandardMaterial color={selected ? "#b8cec5" : hovered ? "#c8d8d0" : "#d2d7d0"} roughness={0.85} />
    </RoundedBox>
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.05, 0]}><ringGeometry args={[1.65, 1.73, 48]} /><meshBasicMaterial color={color} transparent opacity={selected || day >= department.startsAt ? 0.8 : 0.22} /></mesh>
    {!closed ? <>
      <DeskFurniture accent={accent} active={active} reducedMotion={reducedMotion}/>
      <group position={[0,0,1.12]} rotation={[0,Math.PI,0]}><OfficeChair color={accent}/><Representative identity={department.departmentId} position={[0,0,0]} active={active} reducedMotion={reducedMotion}/></group>
      <mesh position={[-1.92,0.055,0]}><boxGeometry args={[0.045,0.01,2.7]}/><meshBasicMaterial color={active ? "#55d6b3" : accent}/></mesh>
    </> : null}
    <LabelAnchor position={[0, 2.65, 0]} element={() => labels.current.get(department.departmentId)} />
  </group>;
}

// The public landing scene is explicitly illustrative, never a company snapshot.
const illustrationDepartments: DepartmentSceneMarker[] = ["Finance","Engineering","Operations","Product","Sales","People"].map((name,index)=>({
  departmentId:`illustration_${name}`,name,label:"Illustrative department",tone:"neutral",position:officePosition(index*2),strength:0,startsAt:Infinity,
}));

function World({day, interactive = true, analyzingDepartmentIds, departments, selectedDepartmentId, onDepartmentSelect, board, participants, onParticipantSelect, resetKey, reducedMotion, dependencyPaths, labels, evening}: OfficeProps & {evening: boolean; reducedMotion: boolean; labels: RefObject<Map<string, HTMLDivElement>>}) {
  const floorSize = board ? 18 : departments?.some(d=>Math.abs(d.position[0])>12 || Math.abs(d.position[2])>12) ? 38 : 28;
  const selected = departments?.find(d => d.departmentId === selectedDepartmentId);
  return <>
    <ambientLight intensity={evening ? 0.65 : 0.95} />
    <hemisphereLight args={[evening ? "#bdcbe0" : "#fff4df", "#738c83", evening ? 0.6 : 0.8]} />
    <directionalLight position={[8,18,6]} intensity={evening ? 1.4 : 2.1} color={evening ? "#ffd7a3" : "#fff1d8"}/>
    <directionalLight position={[-12,7,-8]} intensity={evening ? 0.8 : 0.5} color="#bad8ed"/>
    <OfficeEnvironment size={floorSize} board={Boolean(board)} reducedMotion={reducedMotion} evening={evening}/>
    <MeetingTable reducedMotion={reducedMotion} partition={!board}/>
    {!participants?.length ? Array.from({length:6},(_,index)=>{
      const angle=index*Math.PI/3;
      return <group key={index} position={[Math.sin(angle)*3.85,0,Math.cos(angle)*3.85]} rotation={[0,angle+Math.PI,0]}><OfficeChair/></group>;
    }) : null}
    {!board ? departments?.map(d => <Workstation key={d.departmentId} department={d} day={day} active={Boolean(analyzingDepartmentIds?.includes(d.departmentId))} selected={d.departmentId === selectedDepartmentId} onSelect={onDepartmentSelect} reducedMotion={reducedMotion} labels={labels} />) : null}
    {!board && dependencyPaths?.map((path, index) => {
      const points = path.map(id => departments?.find(d => d.departmentId === id)?.position).filter((p): p is [number, number, number] => Boolean(p));
      return points.length > 1 ? <Line key={index} points={points.map(p => [p[0], 0.35, p[2]])} color="#b97561" lineWidth={2} dashed dashSize={0.3} gapSize={0.15} /> : null;
    })}
    {(participants ?? []).slice(0, 12).map((p, index, all) => {
      const angle = index / Math.max(all.length, 1) * Math.PI * 2;
      const position: [number, number, number] = [Math.sin(angle) * 3.85, 0, Math.cos(angle) * 3.85];
      return <group key={p.key} onClick={event=>{event.stopPropagation();onParticipantSelect?.(p.key);}} position={position} rotation={[0, angle + Math.PI, 0]}>
        <OfficeChair color={wardrobe[characterSeed(p.key)%wardrobe.length]}/>
        <Representative identity={p.key} position={[0, 0, 0]} active={p.status === "analyzing"} reducedMotion={reducedMotion} />
        <mesh position={[0, 0.015, 0]} rotation={[-Math.PI/2,0,0]}><ringGeometry args={[0.5, 0.62, 32]} /><meshBasicMaterial color={p.status === "unavailable" ? "#c17b65" : p.selected ? "#3f7a99" : "#66a78f"} /></mesh>
        {board ? <LabelAnchor position={[0, 1.7, -1.3]} element={() => labels.current.get(p.key)} /> : null}
      </group>;
    })}

    <ContactShadows position={[0,-0.12,0]} opacity={0.32} scale={floorSize+2} blur={2.5} far={8} frames={1} key={`${board}:${departments?.map(d=>d.label).join(":")}:${participants?.length}`} />
    <OrbitControls enabled={interactive} makeDefault enablePan minPolarAngle={0.3} maxPolarAngle={1.25} minDistance={8} maxDistance={65} />
    <CameraFocus reducedMotion={reducedMotion} target={board ? undefined : selected?.position} resetKey={resetKey ?? 0} board={Boolean(board)} wide={floorSize > 28} />
  </>;
}
interface OfficeProps {
  day: number; interactive?: boolean; departments?: DepartmentSceneMarker[]; selectedDepartmentId?: string;
  analyzingDepartmentIds?: string[];
  showAllDepartmentLabels?: boolean; onDepartmentSelect?: (id: string) => void; board?: boolean;
  participants?: OfficeParticipant[]; onParticipantSelect?: (key: string) => void; resetKey?: number; dependencyPaths?: string[][];
}
export function OfficeScene(props: OfficeProps) {
  const [reducedMotion, setReducedMotion] = useState(true);
  const [motionPaused,setMotionPaused] = useState(false);
  const [evening,setEvening] = useState(false);
  const labels = useRef(new Map<string, HTMLDivElement>());
  const {active: loading} = useProgress();
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(query.matches);
    update(); query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  const setLabel = (key: string, element: HTMLDivElement | null) => {if(element) labels.current.set(key,element); else labels.current.delete(key);};
  return <SceneBoundary>
    {loading ? <p role="status" className="absolute left-1/2 top-1/2 z-10 rounded-xl bg-white p-3 text-xs">Loading office…</p> : null}
    <Canvas camera={{position:[25,29,32], fov:38}} dpr={[1,1.5]} gl={{antialias:true,alpha:true}}>
      <Suspense fallback={null}><World {...props} departments={props.interactive===false && !props.departments ? illustrationDepartments : props.departments} labels={labels} reducedMotion={reducedMotion || motionPaused} evening={evening}/></Suspense>
    </Canvas>
    {props.interactive !== false ? <div className={`absolute z-10 flex gap-1 rounded-full border border-white/90 bg-white/90 p-1 text-[10px] text-zinc-600 shadow-sm backdrop-blur ${props.board ? "bottom-3 right-3" : "bottom-40 right-3 sm:bottom-24 sm:right-5"} ${props.selectedDepartmentId ? "lg:right-[460px]" : ""}`}>
      <button type="button" aria-label="Evening lighting" aria-pressed={evening} className="rounded-full px-3 py-2 hover:bg-zinc-100" onClick={()=>setEvening(value=>!value)}>{evening ? "Daylight" : "Evening light"}</button>
      <button type="button" aria-pressed={motionPaused || reducedMotion} disabled={reducedMotion} title={reducedMotion ? "Your device prefers reduced motion" : "Pause decorative movement; simulation results stay unchanged"} className="rounded-full px-3 py-2 hover:bg-zinc-100 disabled:opacity-50" onClick={()=>setMotionPaused(value=>!value)}>{reducedMotion ? "Reduced motion" : motionPaused ? "Resume room motion" : "Pause room motion"}</button>
    </div> : <p className="pointer-events-none absolute bottom-1 inset-x-0 text-center text-[9px] text-zinc-500">Illustrative office · departmental representatives</p>}
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      {!props.board ? props.departments?.map(department => <div key={department.departmentId} ref={element=>setLabel(department.departmentId,element)} className="pointer-events-auto absolute left-0 top-0" style={{visibility:"hidden"}}>
        <button type="button" title={department.name} onClick={() => props.onDepartmentSelect?.(department.departmentId)} aria-pressed={props.selectedDepartmentId===department.departmentId} className={`${props.selectedDepartmentId===department.departmentId ? "w-36 py-2" : "min-w-14 max-w-40 py-1"} rounded-xl border px-2 text-left shadow-sm ${props.selectedDepartmentId===department.departmentId ? "border-zinc-900 bg-zinc-900 text-white" : "border-white bg-white/95 text-zinc-800"}`}>
          <span className="block truncate text-[10px] font-semibold">{department.name}</span>
          {props.selectedDepartmentId===department.departmentId ? <span className="mt-1 block truncate text-[9px] opacity-65">{props.analyzingDepartmentIds?.includes(department.departmentId) ? "Analyzing decision" : props.day<0 ? "Explore department" : props.day>=department.startsAt ? department.label : "No effect reported yet"}</span> : null}
        </button>
      </div>) : props.participants?.map(p=><div key={p.key} ref={element=>setLabel(p.key,element)} className="pointer-events-auto absolute left-0 top-0" style={{visibility:"hidden"}}><button onClick={()=>props.onParticipantSelect?.(p.key)} aria-pressed={Boolean(p.selected)} className={`max-w-32 rounded-lg border px-2 py-1 text-[10px] shadow ${p.selected ? "border-zinc-900 bg-zinc-900 text-white" : "border-white bg-white/95 text-zinc-800"}`}><strong className="block truncate">{p.name}</strong>{p.selected ? <span className="text-[9px]">{p.status==="available" ? "Findings ready" : p.status}</span> : null}</button></div>)}
    </div>
    {!props.board && props.interactive!==false && !props.departments?.length ? <p className="absolute left-1/2 top-1/2 -translate-x-1/2 rounded-xl bg-white p-4 text-sm">No departments configured. Add a department to begin.</p> : null}
  </SceneBoundary>;
}
