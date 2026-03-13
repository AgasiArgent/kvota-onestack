"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { Brush, ArrowUpRight, Type, Undo2, Check, X } from "lucide-react";
import { compressScreenshot } from "../lib/compressScreenshot";

type Tool = "brush" | "arrow" | "text";

interface AnnotationEditorProps {
  screenshotDataUrl: string;
  onSave: (annotatedDataUrl: string) => void;
  onCancel: () => void;
}

const STROKE_COLOR = "#C2410C";
const STROKE_WIDTH = 3;
const ARROW_HEAD_LEN = 18;
const MAX_UNDO = 20;

export function AnnotationEditor({
  screenshotDataUrl,
  onSave,
  onCancel,
}: AnnotationEditorProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [tool, setTool] = useState<Tool>("brush");
  const [imageLoaded, setImageLoaded] = useState(false);
  const undoStackRef = useRef<ImageData[]>([]);
  const drawStateRef = useRef({
    isDrawing: false,
    startX: 0,
    startY: 0,
    arrowSnapshot: null as ImageData | null,
  });
  const bgImageRef = useRef<HTMLImageElement | null>(null);
  const activeInputRef = useRef<HTMLInputElement | null>(null);

  // Clean up orphaned text input on unmount
  useEffect(() => {
    return () => {
      activeInputRef.current?.remove();
    };
  }, []);

  useEffect(() => {
    const img = new Image();
    img.onload = () => {
      bgImageRef.current = img;
      setImageLoaded(true);
    };
    img.src = screenshotDataUrl;
  }, [screenshotDataUrl]);

  // Set canvas dimensions once it renders (after imageLoaded becomes true)
  useEffect(() => {
    const canvas = canvasRef.current;
    const img = bgImageRef.current;
    if (!canvas || !img) return;
    canvas.width = img.width;
    canvas.height = img.height;
  }, [imageLoaded]);

  const getCtx = useCallback(() => {
    const ctx = canvasRef.current?.getContext("2d");
    if (ctx) {
      ctx.strokeStyle = STROKE_COLOR;
      ctx.fillStyle = STROKE_COLOR;
      ctx.lineWidth = STROKE_WIDTH;
      ctx.lineCap = "round";
    }
    return ctx;
  }, []);

  const saveState = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = getCtx();
    if (!canvas || !ctx) return;
    if (undoStackRef.current.length >= MAX_UNDO) undoStackRef.current.shift();
    undoStackRef.current.push(
      ctx.getImageData(0, 0, canvas.width, canvas.height)
    );
  }, [getCtx]);

  const undo = useCallback(() => {
    const ctx = getCtx();
    if (!ctx || undoStackRef.current.length === 0) return;
    const prev = undoStackRef.current.pop()!;
    ctx.putImageData(prev, 0, 0);
  }, [getCtx]);

  const getPos = useCallback((e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left) * (canvas.width / rect.width),
      y: (e.clientY - rect.top) * (canvas.height / rect.height),
    };
  }, []);

  const drawArrow = useCallback(
    (
      ctx: CanvasRenderingContext2D,
      x1: number,
      y1: number,
      x2: number,
      y2: number
    ) => {
      const angle = Math.atan2(y2 - y1, x2 - x1);
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(x2, y2);
      ctx.lineTo(
        x2 - ARROW_HEAD_LEN * Math.cos(angle - Math.PI / 6),
        y2 - ARROW_HEAD_LEN * Math.sin(angle - Math.PI / 6)
      );
      ctx.lineTo(
        x2 - ARROW_HEAD_LEN * Math.cos(angle + Math.PI / 6),
        y2 - ARROW_HEAD_LEN * Math.sin(angle + Math.PI / 6)
      );
      ctx.closePath();
      ctx.fill();
    },
    []
  );

  const handleTextPlace = useCallback(
    (e: React.MouseEvent) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;
      const displayX = e.clientX - rect.left;
      const displayY = e.clientY - rect.top;

      const input = document.createElement("input");
      input.type = "text";
      input.placeholder = "Введите текст...";
      input.style.cssText = `position:fixed;left:${rect.left + displayX}px;top:${rect.top + displayY - 14}px;background:#222;color:${STROKE_COLOR};border:2px solid ${STROKE_COLOR};padding:4px 8px;font:bold 18px sans-serif;z-index:10001;min-width:150px;outline:none;border-radius:4px;`;
      document.body.appendChild(input);
      activeInputRef.current = input;
      input.addEventListener("mousedown", (ev) => ev.stopPropagation());

      let committed = false;
      const commitText = () => {
        if (committed) return;
        committed = true;
        const text = input.value.trim();
        if (text) {
          const ctx = getCtx();
          if (ctx) {
            saveState();
            ctx.font = "bold 20px sans-serif";
            ctx.fillStyle = STROKE_COLOR;
            ctx.fillText(text, displayX * scaleX, displayY * scaleY);
          }
        }
        input.remove();
        activeInputRef.current = null;
      };

      setTimeout(() => {
        input.focus();
        input.addEventListener("blur", commitText);
      }, 50);
      input.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter") commitText();
        if (ev.key === "Escape") {
          committed = true;
          input.remove();
        }
      });
    },
    [getCtx, saveState]
  );

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (tool === "text") {
        handleTextPlace(e);
        return;
      }
      const ctx = getCtx();
      if (!ctx) return;
      const pos = getPos(e);
      const state = drawStateRef.current;
      state.isDrawing = true;
      state.startX = pos.x;
      state.startY = pos.y;
      saveState();
      if (tool === "brush") {
        ctx.beginPath();
        ctx.moveTo(pos.x, pos.y);
      }
      if (tool === "arrow") {
        const canvas = canvasRef.current!;
        state.arrowSnapshot = ctx.getImageData(
          0,
          0,
          canvas.width,
          canvas.height
        );
      }
    },
    [tool, getCtx, getPos, saveState, handleTextPlace]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      const state = drawStateRef.current;
      if (!state.isDrawing) return;
      const ctx = getCtx();
      if (!ctx) return;
      const pos = getPos(e);
      if (tool === "brush") {
        ctx.lineTo(pos.x, pos.y);
        ctx.stroke();
      }
      if (tool === "arrow" && state.arrowSnapshot) {
        ctx.putImageData(state.arrowSnapshot, 0, 0);
        drawArrow(ctx, state.startX, state.startY, pos.x, pos.y);
      }
    },
    [tool, getCtx, getPos, drawArrow]
  );

  const handleMouseUp = useCallback(
    (e: React.MouseEvent) => {
      const state = drawStateRef.current;
      if (!state.isDrawing) return;
      state.isDrawing = false;
      if (tool === "arrow" && state.arrowSnapshot) {
        const ctx = getCtx();
        if (ctx) {
          const pos = getPos(e);
          ctx.putImageData(state.arrowSnapshot, 0, 0);
          drawArrow(ctx, state.startX, state.startY, pos.x, pos.y);
        }
        state.arrowSnapshot = null;
      }
    },
    [tool, getCtx, getPos, drawArrow]
  );

  const handleSave = useCallback(async () => {
    const canvas = canvasRef.current;
    const bgImg = bgImageRef.current;
    if (!canvas || !bgImg) return;

    const finalCanvas = document.createElement("canvas");
    finalCanvas.width = canvas.width;
    finalCanvas.height = canvas.height;
    const ctx = finalCanvas.getContext("2d")!;
    ctx.drawImage(bgImg, 0, 0);
    ctx.drawImage(canvas, 0, 0);

    const rawDataUrl = finalCanvas.toDataURL("image/png");
    const compressed = await compressScreenshot(rawDataUrl);
    onSave(compressed);
  }, [onSave]);

  const tools: { id: Tool; icon: typeof Brush; label: string }[] = [
    { id: "brush", icon: Brush, label: "Кисть" },
    { id: "arrow", icon: ArrowUpRight, label: "Стрелка" },
    { id: "text", icon: Type, label: "Текст" },
  ];

  return (
    <div className="fixed inset-0 z-[9999] bg-neutral-900 flex flex-col">
      <div className="flex items-center gap-2 px-3 py-2 bg-neutral-800 shrink-0">
        {tools.map((t) => (
          <button
            key={t.id}
            onClick={() => setTool(t.id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-sm ${
              tool === t.id
                ? "bg-red-500/80 text-white"
                : "bg-neutral-700 text-neutral-300 hover:bg-neutral-600"
            }`}
            title={t.label}
          >
            <t.icon size={16} />
            {t.label}
          </button>
        ))}
        <button
          onClick={undo}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm bg-neutral-700 text-neutral-400 hover:bg-neutral-600 ml-2"
          title="Отменить"
        >
          <Undo2 size={16} />
        </button>
        <div className="flex-1" />
        <button
          onClick={handleSave}
          className="flex items-center gap-1.5 px-4 py-1.5 rounded text-sm bg-green-600 text-white hover:bg-green-500 font-medium"
        >
          <Check size={16} /> Готово
        </button>
        <button
          onClick={onCancel}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm bg-neutral-700 text-neutral-400 hover:bg-neutral-600"
        >
          <X size={16} /> Отмена
        </button>
      </div>

      <div className="flex-1 overflow-auto flex items-start justify-center p-3">
        {imageLoaded && (
          <canvas
            ref={canvasRef}
            className="max-w-full cursor-crosshair"
            style={{
              backgroundImage: `url(${screenshotDataUrl})`,
              backgroundSize: "100% 100%",
            }}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
          />
        )}
      </div>
    </div>
  );
}
