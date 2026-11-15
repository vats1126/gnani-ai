/**
 * Canvas utility functions for normalized stroke storage, High-DPI rendering,
 * and high-fidelity snapshot export for multimodal AI ingestion.
 */

export const PAPER_BG = '#FAF8F5';
export const PAPER_WHITE = '#FFFFFF';

/**
 * Normalizes a pixel point (px, py) relative to canvas CSS dimensions (width, height).
 * Ensures coordinates stay strictly in [0, 1].
 */
export function normalizePoint(px, py, width, height) {
  const safeW = width > 0 ? width : 1;
  const safeH = height > 0 ? height : 1;
  return {
    x: Math.max(0, Math.min(1, px / safeW)),
    y: Math.max(0, Math.min(1, py / safeH)),
  };
}

/**
 * Normalizes line width relative to the min canvas dimension so stroke weights
 * remain proportional across different screen resolutions and orientations.
 */
export function normalizeLineWidth(lineWidthPx, width, height) {
  const baseDim = Math.min(width, height) || 600;
  return lineWidthPx / baseDim;
}

/**
 * Denormalizes line width for the current canvas size.
 */
export function denormalizeLineWidth(normWidth, width, height, minPx = 1.5, maxPx = 40) {
  const baseDim = Math.min(width, height) || 600;
  const px = normWidth * baseDim;
  return Math.max(minPx, Math.min(maxPx, px));
}

/**
 * Redraws all normalized strokes onto an HTML5 canvas element with high-DPI scaling.
 * 
 * @param {HTMLCanvasElement} canvas
 * @param {Array} strokes - Array of normalized stroke objects
 * @param {Object} [options]
 * @param {string} [options.bgColor=PAPER_BG]
 * @param {number} [options.customWidth]
 * @param {number} [options.customHeight]
 * @param {number} [options.dpr]
 */
export function redrawCanvas(canvas, strokes, options = {}) {
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const dpr = options.dpr || window.devicePixelRatio || 1;
  const cssWidth = options.customWidth || canvas.clientWidth || 600;
  const cssHeight = options.customHeight || canvas.clientHeight || 400;

  const targetWidth = Math.floor(cssWidth * dpr);
  const targetHeight = Math.floor(cssHeight * dpr);

  if (canvas.width !== targetWidth || canvas.height !== targetHeight) {
    canvas.width = targetWidth;
    canvas.height = targetHeight;
  }

  // Reset transform and apply DPR scaling
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  // Fill solid light paper-like background
  const bgColor = options.bgColor || PAPER_BG;
  ctx.fillStyle = bgColor;
  ctx.fillRect(0, 0, cssWidth, cssHeight);

  if (!strokes || strokes.length === 0) {
    return;
  }

  // Render each stroke
  for (const stroke of strokes) {
    if (!stroke.points || stroke.points.length === 0) continue;

    ctx.save();
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    const strokeWidth = denormalizeLineWidth(
      stroke.lineWidth || 0.005,
      cssWidth,
      cssHeight
    );
    ctx.lineWidth = strokeWidth;

    if (stroke.tool === 'eraser') {
      // Draw with paper background color to erase
      ctx.strokeStyle = bgColor;
    } else {
      ctx.strokeStyle = stroke.color || '#1E293B';
    }

    const points = stroke.points;
    if (points.length === 1) {
      // Single tap / dot
      const pt = points[0];
      const cx = pt.x * cssWidth;
      const cy = pt.y * cssHeight;
      ctx.fillStyle = ctx.strokeStyle;
      ctx.beginPath();
      ctx.arc(cx, cy, strokeWidth / 2, 0, Math.PI * 2);
      ctx.fill();
    } else {
      ctx.beginPath();
      ctx.moveTo(points[0].x * cssWidth, points[0].y * cssHeight);

      // Smooth curve through midpoints
      for (let i = 1; i < points.length; i++) {
        const p0 = points[i - 1];
        const p1 = points[i];
        const midX = ((p0.x + p1.x) / 2) * cssWidth;
        const midY = ((p0.y + p1.y) / 2) * cssHeight;
        ctx.quadraticCurveTo(p0.x * cssWidth, p0.y * cssHeight, midX, midY);
      }
      const last = points[points.length - 1];
      ctx.lineTo(last.x * cssWidth, last.y * cssHeight);
      ctx.stroke();
    }

    ctx.restore();
  }
}

/**
 * Renders the current strokes onto an offscreen canvas with solid white background
 * (preventing black artifacts in JPEG compression) and exports a base64 JPEG data URL.
 * 
 * @param {HTMLCanvasElement} canvas
 * @param {Array} strokes
 * @param {number} [maxDim=1400] - Max width or height in pixels
 * @param {number} [quality=0.8] - JPEG quality (0.0 - 1.0)
 * @returns {{ dataUrl: string, bytes: number, width: number, height: number, strokeCount: number }}
 */
export function exportCanvasSnapshot(canvas, strokes, maxDim = 1400, quality = 0.8) {
  const cssWidth = canvas ? (canvas.clientWidth || 800) : 800;
  const cssHeight = canvas ? (canvas.clientHeight || 600) : 600;

  // Scale dimensions while preserving aspect ratio
  let targetW = cssWidth;
  let targetH = cssHeight;

  if (targetW > maxDim || targetH > maxDim) {
    if (targetW >= targetH) {
      targetH = Math.round((targetH / targetW) * maxDim);
      targetW = maxDim;
    } else {
      targetW = Math.round((targetW / targetH) * maxDim);
      targetH = maxDim;
    }
  }

  // Ensure minimum dimensions
  targetW = Math.max(300, targetW);
  targetH = Math.max(200, targetH);

  // Offscreen canvas for export
  const offscreen = document.createElement('canvas');
  offscreen.width = targetW;
  offscreen.height = targetH;

  const ctx = offscreen.getContext('2d');
  // Solid white background ensures math expressions and lines stand out cleanly for OCR
  ctx.fillStyle = PAPER_WHITE;
  ctx.fillRect(0, 0, targetW, targetH);

  // Render strokes at 1x DPR on the offscreen canvas
  redrawCanvas(offscreen, strokes, {
    bgColor: PAPER_WHITE,
    customWidth: targetW,
    customHeight: targetH,
    dpr: 1,
  });

  const dataUrl = offscreen.toDataURL('image/jpeg', quality);

  // Calculate approximate byte size of base64
  const base64Index = dataUrl.indexOf(';base64,');
  const base64Str = base64Index !== -1 ? dataUrl.slice(base64Index + 8) : dataUrl;
  const approxBytes = Math.round((base64Str.length * 3) / 4);

  return {
    dataUrl,
    bytes: approxBytes,
    width: targetW,
    height: targetH,
    strokeCount: (strokes || []).length,
  };
}

/**
 * Three-minute live hackathon pitch demo presets (Section 15).
 * Generates clean, responsive normalized stroke sequences for instant loading.
 */
function createStroke(points, color = '#0F172A', lineWidth = 0.007) {
  return {
    tool: 'pen',
    color,
    lineWidth,
    points,
  };
}

export const DEMO_PRESETS = {
  step1_problem: {
    label: 'Step 1: Problem (2x = 8)',
    subject: 'Maths',
    suggestedText: 'How do I solve this equation: 2x = 8?',
    action: 'ask',
    getStrokes: () => [
      // '2'
      createStroke([
        { x: 0.26, y: 0.44 }, { x: 0.28, y: 0.41 }, { x: 0.32, y: 0.40 },
        { x: 0.34, y: 0.43 }, { x: 0.33, y: 0.47 }, { x: 0.27, y: 0.54 },
        { x: 0.35, y: 0.54 }
      ]),
      // 'x'
      createStroke([{ x: 0.38, y: 0.44 }, { x: 0.44, y: 0.54 }]),
      createStroke([{ x: 0.44, y: 0.44 }, { x: 0.38, y: 0.54 }]),
      // '='
      createStroke([{ x: 0.48, y: 0.47 }, { x: 0.54, y: 0.47 }]),
      createStroke([{ x: 0.48, y: 0.51 }, { x: 0.54, y: 0.51 }]),
      // '8'
      createStroke([
        { x: 0.61, y: 0.43 }, { x: 0.58, y: 0.41 }, { x: 0.64, y: 0.41 },
        { x: 0.61, y: 0.46 }, { x: 0.57, y: 0.51 }, { x: 0.65, y: 0.51 },
        { x: 0.61, y: 0.46 }, { x: 0.61, y: 0.43 }
      ]),
    ],
  },

  step2_error: {
    label: 'Step 2: Error Step (x = 8)',
    subject: 'Maths',
    suggestedText: '2x = 8, x = 8',
    action: 'check_work',
    getStrokes: () => [
      // Line 1: '2x = 8'
      createStroke([
        { x: 0.26, y: 0.34 }, { x: 0.28, y: 0.31 }, { x: 0.32, y: 0.30 },
        { x: 0.34, y: 0.33 }, { x: 0.33, y: 0.37 }, { x: 0.27, y: 0.44 },
        { x: 0.35, y: 0.44 }
      ]),
      createStroke([{ x: 0.38, y: 0.34 }, { x: 0.44, y: 0.44 }]),
      createStroke([{ x: 0.44, y: 0.34 }, { x: 0.38, y: 0.44 }]),
      createStroke([{ x: 0.48, y: 0.37 }, { x: 0.54, y: 0.37 }]),
      createStroke([{ x: 0.48, y: 0.41 }, { x: 0.54, y: 0.41 }]),
      createStroke([
        { x: 0.61, y: 0.33 }, { x: 0.58, y: 0.31 }, { x: 0.64, y: 0.31 },
        { x: 0.61, y: 0.36 }, { x: 0.57, y: 0.41 }, { x: 0.65, y: 0.41 },
        { x: 0.61, y: 0.36 }, { x: 0.61, y: 0.33 }
      ]),

      // Line 2: 'x = 8' (Student error: forgot to divide right side)
      createStroke([{ x: 0.38, y: 0.54 }, { x: 0.44, y: 0.64 }], '#DC2626'),
      createStroke([{ x: 0.44, y: 0.54 }, { x: 0.38, y: 0.64 }], '#DC2626'),
      createStroke([{ x: 0.48, y: 0.57 }, { x: 0.54, y: 0.57 }], '#DC2626'),
      createStroke([{ x: 0.48, y: 0.61 }, { x: 0.54, y: 0.61 }], '#DC2626'),
      createStroke([
        { x: 0.61, y: 0.53 }, { x: 0.58, y: 0.51 }, { x: 0.64, y: 0.51 },
        { x: 0.61, y: 0.56 }, { x: 0.57, y: 0.61 }, { x: 0.65, y: 0.61 },
        { x: 0.61, y: 0.56 }, { x: 0.61, y: 0.53 }
      ], '#DC2626'),
    ],
  },

  step3_correct: {
    label: 'Step 3: Correct Step (x = 4)',
    subject: 'Maths',
    suggestedText: '2x = 8, x = 4',
    action: 'check_work',
    getStrokes: () => [
      // Line 1: '2x = 8'
      createStroke([
        { x: 0.26, y: 0.34 }, { x: 0.28, y: 0.31 }, { x: 0.32, y: 0.30 },
        { x: 0.34, y: 0.33 }, { x: 0.33, y: 0.37 }, { x: 0.27, y: 0.44 },
        { x: 0.35, y: 0.44 }
      ]),
      createStroke([{ x: 0.38, y: 0.34 }, { x: 0.44, y: 0.44 }]),
      createStroke([{ x: 0.44, y: 0.34 }, { x: 0.38, y: 0.44 }]),
      createStroke([{ x: 0.48, y: 0.37 }, { x: 0.54, y: 0.37 }]),
      createStroke([{ x: 0.48, y: 0.41 }, { x: 0.54, y: 0.41 }]),
      createStroke([
        { x: 0.61, y: 0.33 }, { x: 0.58, y: 0.31 }, { x: 0.64, y: 0.31 },
        { x: 0.61, y: 0.36 }, { x: 0.57, y: 0.41 }, { x: 0.65, y: 0.41 },
        { x: 0.61, y: 0.36 }, { x: 0.61, y: 0.33 }
      ]),

      // Line 2: 'x = 4' (Correct step)
      createStroke([{ x: 0.38, y: 0.54 }, { x: 0.44, y: 0.64 }], '#16A34A'),
      createStroke([{ x: 0.44, y: 0.54 }, { x: 0.38, y: 0.64 }], '#16A34A'),
      createStroke([{ x: 0.48, y: 0.57 }, { x: 0.54, y: 0.57 }], '#16A34A'),
      createStroke([{ x: 0.48, y: 0.61 }, { x: 0.54, y: 0.61 }], '#16A34A'),
      // '4'
      createStroke([{ x: 0.62, y: 0.51 }, { x: 0.58, y: 0.58 }, { x: 0.65, y: 0.58 }], '#16A34A'),
      createStroke([{ x: 0.63, y: 0.51 }, { x: 0.63, y: 0.64 }], '#16A34A'),
    ],
  },

  science_gravity: {
    label: 'Science: Gravity Concept',
    subject: 'Science',
    suggestedText: 'Why do objects fall towards Earth?',
    action: 'ask',
    getStrokes: () => [
      // Earth curved surface
      createStroke([
        { x: 0.15, y: 0.82 }, { x: 0.35, y: 0.77 }, { x: 0.50, y: 0.76 },
        { x: 0.65, y: 0.77 }, { x: 0.85, y: 0.82 }
      ], '#16A34A', 0.012),
      // Falling Apple
      createStroke([
        { x: 0.48, y: 0.35 }, { x: 0.52, y: 0.33 }, { x: 0.54, y: 0.36 },
        { x: 0.53, y: 0.40 }, { x: 0.49, y: 0.40 }, { x: 0.48, y: 0.35 }
      ], '#DC2626', 0.009),
      // Downward Gravity Arrow
      createStroke([{ x: 0.51, y: 0.44 }, { x: 0.51, y: 0.68 }], '#2563EB', 0.008),
      createStroke([{ x: 0.47, y: 0.63 }, { x: 0.51, y: 0.68 }, { x: 0.55, y: 0.63 }], '#2563EB', 0.008),
    ],
  },
};


