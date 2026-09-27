"use client";

import { RoundedBox } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useRef } from "react";
import { Group, MeshStandardMaterial } from "three";

/** Furniture and ambient decoration never encode staffing, progress, or business outcomes. */
export function OfficePlant({position, scale = 1, reducedMotion}: {position: [number,number,number]; scale?: number; reducedMotion: boolean}) {
  const leaves = useRef<Group>(null);
  useFrame(({clock}) => {
    if (leaves.current) leaves.current.rotation.z = reducedMotion ? 0 : Math.sin(clock.elapsedTime * 0.65 + position[0]) * 0.025;
  });
  return <group position={position} scale={scale}>
    <mesh position={[0,0.25,0]}><cylinderGeometry args={[0.3,0.23,0.5,12]}/><meshStandardMaterial color="#e8d9c4" roughness={0.85}/></mesh>
    <group ref={leaves} position={[0,0.45,0]}>
      <mesh position={[0,0.4,0]}><cylinderGeometry args={[0.035,0.05,0.85,6]}/><meshStandardMaterial color="#59674b"/></mesh>
      {[0,1,2,3,4].map(i=><group key={i} rotation={[0,i*2.4,0]} position={[0,0.12+i*0.14,0]}><mesh position={[0.15,0.18,0]} rotation={[0,0,-0.55]} scale={[0.17,0.38,0.1]}><sphereGeometry args={[1,8,6]}/><meshStandardMaterial color={i%2 ? "#688967" : "#375e4e"} roughness={0.9}/></mesh></group>)}
    </group>
  </group>;
}

export function OfficeChair({color = "#38545b"}: {color?: string}) {
  return <group>
    <RoundedBox args={[0.7,0.12,0.62]} radius={0.05} position={[0,0.63,0]}><meshStandardMaterial color={color} roughness={0.85}/></RoundedBox>
    <RoundedBox args={[0.7,0.62,0.12]} radius={0.05} position={[0,0.99,-0.29]}><meshStandardMaterial color={color} roughness={0.85}/></RoundedBox>
    {[-1,1].map(side=><mesh key={side} position={[side*0.37,0.8,0]}><boxGeometry args={[0.045,0.05,0.38]}/><meshStandardMaterial color="#293a40" metalness={0.4}/></mesh>)}
    <mesh position={[0,0.31,0]}><cylinderGeometry args={[0.055,0.07,0.5,8]}/><meshStandardMaterial color="#788385" metalness={0.6} roughness={0.3}/></mesh>
    {[0,1,2,3,4].map(i=><group key={i} rotation={[0,i*Math.PI*0.4,0]}><mesh position={[0,0.065,0.18]}><boxGeometry args={[0.045,0.06,0.38]}/><meshStandardMaterial color="#56676b"/></mesh><mesh position={[0,0.04,0.35]}><sphereGeometry args={[0.055,6,6]}/><meshStandardMaterial color="#273338"/></mesh></group>)}
  </group>;
}

export function DeskFurniture({accent, active, reducedMotion}: {accent: string; active: boolean; reducedMotion: boolean}) {
  const screen = useRef<MeshStandardMaterial>(null);
  useFrame(({clock})=>{
    if (screen.current) screen.current.emissiveIntensity = active && !reducedMotion ? 0.5 + Math.sin(clock.elapsedTime*2)*0.2 : 0.18;
  });
  return <group>
    <RoundedBox args={[2.85,0.65,0.08]} radius={0.04} position={[0,1.37,-0.76]}><meshStandardMaterial color={accent} roughness={1}/></RoundedBox>
    <RoundedBox args={[2.7,0.13,1.3]} radius={0.06} position={[0,1.06,0]}><meshStandardMaterial color="#cdb38b" roughness={0.7}/></RoundedBox>
    {[-1,1].map(side=><group key={side} position={[side*1.13,0,0]}><mesh position={[0,0.51,0]}><boxGeometry args={[0.085,1.02,0.85]}/><meshStandardMaterial color="#ecede7" metalness={0.3}/></mesh></group>)}
    <RoundedBox args={[0.85,0.015,0.55]} radius={0.02} position={[0,1.137,0.22]}><meshStandardMaterial color={accent}/></RoundedBox>
    <mesh position={[0,1.145,0.26]}><boxGeometry args={[0.58,0.025,0.22]}/><meshStandardMaterial color="#d9dfdf"/></mesh>
    {[0,1,2].map(row=><mesh key={row} position={[0,1.16,0.2+row*0.055]}><boxGeometry args={[0.51,0.004,0.012]}/><meshStandardMaterial color="#829597"/></mesh>)}
    <mesh position={[0.53,1.15,0.3]} scale={[0.075,0.025,0.11]}><sphereGeometry args={[1,8,6]}/><meshStandardMaterial color="#eceee8"/></mesh>
    <mesh position={[0,1.3,-0.35]}><boxGeometry args={[0.06,0.38,0.055]}/><meshStandardMaterial color="#3b5058"/></mesh>
    <RoundedBox args={[1.15,0.66,0.075]} radius={0.035} position={[0,1.65,-0.35]}><meshStandardMaterial color="#253940" roughness={0.5}/></RoundedBox>
    <mesh position={[0,1.65,-0.307]}><planeGeometry args={[1.04,0.54]}/><meshStandardMaterial ref={screen} color="#173a49" emissive={active ? "#4adbb9" : "#407984"} emissiveIntensity={0.18}/></mesh>
    {/* Abstract desktop lines are decoration, never a fabricated progress chart. */}
    {[0,1,2].map(row=><mesh key={row} position={[-0.16,1.77-row*0.12,-0.3]}><planeGeometry args={[row===1?0.4:0.58,0.025]}/><meshBasicMaterial color={active ? "#8ce7ce" : "#709ba6"}/></mesh>)}
    <mesh position={[-0.95,1.23,0.3]}><cylinderGeometry args={[0.095,0.08,0.2,12]}/><meshStandardMaterial color="#f3eee3"/></mesh>
    <mesh position={[-0.95,1.333,0.3]} rotation={[-Math.PI/2,0,0]}><circleGeometry args={[0.075,12]}/><meshStandardMaterial color="#5c4637"/></mesh>
    <RoundedBox args={[0.32,0.04,0.43]} radius={0.02} position={[0.97,1.15,0.24]} rotation={[0,0.18,0]}><meshStandardMaterial color={accent}/></RoundedBox>
    <OfficePlant position={[-1.05,1.13,-0.4]} scale={0.32} reducedMotion={reducedMotion}/>
  </group>;
}

function Lounge({position}: {position: [number,number,number]}) {
  return <group position={position}>
    <RoundedBox args={[4.7,0.035,3.7]} radius={0.3} position={[0,-0.08,0.45]}><meshStandardMaterial color="#aeb9ac" roughness={1}/></RoundedBox>
    <RoundedBox args={[3.6,0.5,1.1]} radius={0.16} position={[0,0.38,-0.6]}><meshStandardMaterial color="#416463" roughness={1}/></RoundedBox>
    <RoundedBox args={[3.6,0.75,0.27]} radius={0.1} position={[0,0.87,-1]}><meshStandardMaterial color="#416463" roughness={1}/></RoundedBox>
    {[-1,1].map(side=><RoundedBox key={side} args={[0.28,0.5,1.1]} radius={0.08} position={[side*1.68,0.72,-0.6]}><meshStandardMaterial color="#416463"/></RoundedBox>)}
    {[-1,0,1].map(i=><RoundedBox key={i} args={[0.92,0.12,0.83]} radius={0.07} position={[i*1.04,0.68,-0.48]}><meshStandardMaterial color={i===0 ? "#d5b079" : "#73908a"}/></RoundedBox>)}
    <mesh position={[0,0.53,1.1]}><cylinderGeometry args={[0.85,0.85,0.12,32]}/><meshStandardMaterial color="#d3bb97"/></mesh>
    <mesh position={[0,0.23,1.1]}><cylinderGeometry args={[0.36,0.46,0.5,16]}/><meshStandardMaterial color="#485b5e"/></mesh>
    <RoundedBox args={[0.45,0.05,0.55]} radius={0.015} position={[0.1,0.62,1.1]} rotation={[0,0.3,0]}><meshStandardMaterial color="#ede8dd"/></RoundedBox>
  </group>;
}

export function OfficeEnvironment({size, board, reducedMotion, evening}: {size: number; board: boolean; reducedMotion: boolean; evening: boolean}) {
  const edge=size/2;
  return <group>
    <RoundedBox args={[size,0.5,size]} radius={0.15} position={[0,-0.39,0]}><meshStandardMaterial color="#b4c0b9" roughness={0.75}/></RoundedBox>
    <mesh position={[0,-0.12,0]} rotation={[-Math.PI/2,0,0]}><planeGeometry args={[size-0.12,size-0.12]}/><meshStandardMaterial color={evening ? "#abb6b3" : "#e2dfd5"} roughness={0.9}/></mesh>
    {Array.from({length:Math.floor(size/1.4)},(_,i)=><mesh key={i} position={[-edge+0.7+i*1.4,-0.113,0]}><boxGeometry args={[0.012,0.005,size-0.2]}/><meshStandardMaterial color="#c4c4b9"/></mesh>)}
    <RoundedBox args={[size,0.6,0.22]} radius={0.05} position={[0,0.15,-edge]}><meshStandardMaterial color="#b0bcb4"/></RoundedBox>
    <RoundedBox args={[0.22,0.6,size]} radius={0.05} position={[-edge,0.15,0]}><meshStandardMaterial color="#b0bcb4"/></RoundedBox>
    {Array.from({length:6},(_,i)=><group key={i} position={[-edge+(i+0.5)*size/6,1.95,-edge]}>
      <mesh><boxGeometry args={[size/6-0.08,3,0.055]}/><meshStandardMaterial color="#b6d9dd" transparent opacity={0.2} roughness={0.2} depthWrite={false}/></mesh>
      <mesh position={[-size/12,0,0]}><boxGeometry args={[0.07,3.1,0.1]}/><meshStandardMaterial color="#50686c" metalness={0.4}/></mesh>
      <mesh position={[0,1.52,0]}><boxGeometry args={[size/6,0.08,0.1]}/><meshStandardMaterial color="#50686c"/></mesh>
    </group>)}
    <group position={[-edge+0.03,1.65,-edge+3]}>
      {Array.from({length:13},(_,i)=><mesh key={i} position={[0,0,i*0.25-1.5]}><boxGeometry args={[0.2,3.1,0.11]}/><meshStandardMaterial color="#b49369" roughness={0.85}/></mesh>)}
    </group>
    {[-1,1].flatMap(x=>[-1,1].map(z=><OfficePlant key={`${x}:${z}`} position={[x*(edge-0.65),-0.1,z*(edge-0.65)]} scale={1.6} reducedMotion={reducedMotion}/>))}
    {!board ? <>
      <Lounge position={[-edge+3,0,-edge+3]}/>
      <group position={[edge-3,0,-edge+1.1]}>
        <RoundedBox args={[4.4,1.1,0.85]} radius={0.07} position={[0,0.45,0]}><meshStandardMaterial color="#b9956d"/></RoundedBox>
        <RoundedBox args={[4.6,0.12,1]} radius={0.04} position={[0,1.06,0]}><meshStandardMaterial color="#eeeae0"/></RoundedBox>
        <RoundedBox args={[0.6,0.6,0.48]} radius={0.04} position={[0.8,1.4,-0.05]}><meshStandardMaterial color="#31494f" metalness={0.35}/></RoundedBox>
        <mesh position={[0.8,1.39,0.2]}><boxGeometry args={[0.39,0.22,0.02]}/><meshStandardMaterial color="#baccc8"/></mesh>
        <OfficePlant position={[-1.5,1.12,0]} scale={0.65} reducedMotion={reducedMotion}/>
        {[-0.2,0.1].map(x=><mesh key={x} position={[x,1.22,0.18]}><cylinderGeometry args={[0.08,0.065,0.19,10]}/><meshStandardMaterial color="#eee8dc"/></mesh>)}
      </group>
    </> : null}
    <mesh position={[0,0.48,-edge+0.15]}><boxGeometry args={[size-0.6,0.035,0.035]}/><meshBasicMaterial color={evening ? "#ffcb86" : "#f8e6bb"}/></mesh>
    <mesh position={[-edge+0.15,0.48,0]}><boxGeometry args={[0.035,0.035,size-0.6]}/><meshBasicMaterial color={evening ? "#ffcb86" : "#f8e6bb"}/></mesh>
  </group>;
}

export function MeetingTable({reducedMotion, partition}: {reducedMotion: boolean; partition: boolean}) {
  return <group>
    {partition ? [-1,0,1].map(i=><group key={i} position={[i*2.9,1.45,-5.9]}>
      <mesh><boxGeometry args={[2.82,2.9,0.04]}/><meshStandardMaterial color="#b9d9d1" transparent opacity={0.16} depthWrite={false} roughness={0.2}/></mesh>
      <mesh position={[-1.45,0,0]}><boxGeometry args={[0.035,2.9,0.055]}/><meshStandardMaterial color="#718781"/></mesh>
      <mesh position={[0,1.45,0]}><boxGeometry args={[2.9,0.04,0.055]}/><meshStandardMaterial color="#718781"/></mesh>
    </group>) : null}
    <mesh rotation={[-Math.PI/2,0,0]} position={[0,-0.09,0]}><circleGeometry args={[5.6,64]}/><meshStandardMaterial color="#587371" roughness={1}/></mesh>
    <mesh rotation={[-Math.PI/2,0,0]} position={[0,-0.08,0]}><ringGeometry args={[5.35,5.37,64]}/><meshBasicMaterial color="#8ea6a0"/></mesh>
    <mesh position={[0,0.84,0]}><cylinderGeometry args={[3.3,3.3,0.18,64]}/><meshStandardMaterial color="#bea17b" roughness={0.65}/></mesh>
    <mesh position={[0,0.945,0]}><cylinderGeometry args={[3.22,3.22,0.035,64]}/><meshStandardMaterial color="#e9e6dc" roughness={0.65}/></mesh>
    <mesh position={[0,0.38,0]}><cylinderGeometry args={[1.2,1.5,0.76,32]}/><meshStandardMaterial color="#344e52" metalness={0.25}/></mesh>
    <mesh rotation={[-Math.PI/2,0,0]} position={[0,0.969,0]}><circleGeometry args={[0.65,32]}/><meshStandardMaterial color="#b3c4bb"/></mesh>
    <OfficePlant position={[0,0.98,0]} scale={0.6} reducedMotion={reducedMotion}/>
    {[0,1,2,3].map(i=><group key={i} rotation={[0,i*Math.PI/2,0]}><RoundedBox args={[0.48,0.025,0.62]} radius={0.025} position={[0,0.98,2.5]}><meshStandardMaterial color="#354f57"/></RoundedBox><mesh position={[0.45,1.08,2.5]}><cylinderGeometry args={[0.07,0.065,0.21,10]}/><meshStandardMaterial color="#eee8dc"/></mesh></group>)}
  </group>;
}
