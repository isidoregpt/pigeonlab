import { useRef, useEffect } from "react";

interface HeatmapCanvasProps {
  grid: number[][];
  accent?: [number, number, number];
  emptyMessage?: string;
  className?: string;
}

export default function HeatmapCanvas({
  grid,
  accent = [13, 148, 136],
  emptyMessage = "No heatmap data available.",
  className,
}: HeatmapCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rows = grid.length;
  const cols = rows > 0 ? grid[0].length : 0;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || rows === 0 || cols === 0) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const cellW = canvas.width / cols;
    const cellH = canvas.height / rows;

    // Find max value
    let max = 0;
    for (const row of grid) for (const v of row) if (v > max) max = v;
    if (max === 0) max = 1;

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const t = grid[r][c] / max;
        const red = Math.round(255 + (accent[0] - 255) * t);
        const green = Math.round(255 + (accent[1] - 255) * t);
        const blue = Math.round(255 + (accent[2] - 255) * t);
        ctx.fillStyle = `rgb(${red},${green},${blue})`;
        ctx.fillRect(c * cellW, r * cellH, cellW + 0.5, cellH + 0.5);
      }
    }
  }, [grid, rows, cols, accent]);

  if (rows === 0) {
    return (
      <p className="text-sm text-text-secondary py-6 text-center">
        {emptyMessage}
      </p>
    );
  }

  return (
    <canvas
      ref={canvasRef}
      width={cols * 6}
      height={rows * 6}
      className={`w-full rounded-lg border border-border ${className ?? ""}`}
      style={{ imageRendering: "pixelated", aspectRatio: `${cols}/${rows}` }}
    />
  );
}
