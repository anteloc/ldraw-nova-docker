export type Cell = [number, number, number, number];
export type EditTool = "orbit" | "add" | "paint" | "erase";
export const cellKey = (cell: Cell) => cell.slice(0, 3).join(",");

/** BrickBuilder's editor convention: x/y horizontal, z in 1.2-stud layers. */
export function editCells(cells: Cell[], index: number, tool: EditTool, colour: number, normal: number[]): Cell[] {
  const hit = cells[index];
  if (!hit || tool === "orbit") return cells;
  if (tool === "erase") return cells.length > 1 ? cells.filter((_, i) => i !== index) : cells;
  if (tool === "paint") return hit[3] === colour ? cells : cells.map((c, i) => i === index ? [c[0], c[1], c[2], colour] : c);
  const axis = normal.reduce((best, n, i) => Math.abs(n) > Math.abs(normal[best]) ? i : best, 0);
  const next: Cell = [...hit];
  next[axis] += Math.sign(normal[axis]); next[3] = colour;
  if (cells.length >= 65536 || cells.some(c => cellKey(c) === cellKey(next))) return cells;
  const all = [...cells, next];
  const bounds = [0, 1, 2].map(i => all.reduce((max, c) => Math.max(max, c[i]), -Infinity) - all.reduce((min, c) => Math.min(min, c[i]), Infinity) + 1);
  if (Math.max(...bounds) > 96 || bounds[0] * bounds[1] * bounds[2] > 262144) return cells;
  return all;
}
