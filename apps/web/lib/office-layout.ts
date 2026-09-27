/** Visual slots are independent of headcount and of the order of API responses. */
export function reconcileSlots(previous: Record<string, number>, ids: string[]): Record<string, number> {
  const slots = { ...previous };
  let next = Math.max(-1, ...Object.values(slots)) + 1;
  for (const id of [...ids].sort()) if (slots[id] === undefined) slots[id] = next++;
  return slots;
}

export function officePosition(slot: number): [number, number, number] {
  const local = slot % 24;
  const outer = local >= 12;
  const angle = ((local % 12) / 12) * Math.PI * 2;
  const radius = outer ? 15.5 : 9.5;
  return [Math.sin(angle) * radius, 0.08, Math.cos(angle) * radius];
}
