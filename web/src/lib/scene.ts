import { JAW, MOUTH_NAMES, type MouthName } from "@/lib/mouths";

export const SCENE_W = 1280;
export const SCENE_H = 720;

export const BACKGROUNDS = [
  { id: "coffee", label: "Coffee shop", href: "/backgrounds/coffee-shop.jpg?v=2" },
  { id: "library", label: "Library", href: "/backgrounds/library.jpg?v=2" },
] as const;

export type BackgroundId = (typeof BACKGROUNDS)[number]["id"];

const CAST_IDS = ["adam", "ben", "corey", "emily", "abby-r", "abby-s"] as const;

export type ScenePerson = {
  id: string;
  name: string;
  body: string;
  mouths: Partial<Record<MouthName, string>>;
  mouthX: number;
  mouthY: number;
  mouthScale: number;
};

export function stockCast(): ScenePerson[] {
  return CAST_IDS.map((id) => ({
    id,
    name: id,
    body: `/cast/layers/${id}.png`,
    mouths: Object.fromEntries(MOUTH_NAMES.map((name) => [name, `/cast/mouth-parts/${id}/${name}.png`])),
    mouthX: 50,
    mouthY: 34,
    mouthScale: 14,
  }));
}

const keyed = new Map<string, HTMLCanvasElement>();

function magenta(r: number, g: number, b: number) {
  return r > 170 && b > 70 && g < 140 && r - g > 60 && r > b * 0.7;
}

function plateIsMagenta(img: CanvasImageSource, sw: number, sh: number) {
  const sample = document.createElement("canvas");
  sample.width = 2;
  sample.height = 2;
  const ctx = sample.getContext("2d", { willReadFrequently: true });
  if (!ctx) return false;
  ctx.drawImage(img, 0, 0, sw, sh, 0, 0, 2, 2);
  const pixel = ctx.getImageData(0, 0, 1, 1).data;
  return magenta(pixel[0] ?? 0, pixel[1] ?? 0, pixel[2] ?? 0);
}

function keyedImage(img: HTMLImageElement, w: number, h: number): CanvasImageSource {
  if (!plateIsMagenta(img, img.width, img.height)) return img;
  const key = `${img.src}|${w}x${h}`;
  const cached = keyed.get(key);
  if (cached) return cached;
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, w);
  canvas.height = Math.max(1, h);
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) return img;
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  const frame = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const data = frame.data;
  for (let i = 0; i < data.length; i += 4) {
    if (magenta(data[i] ?? 0, data[i + 1] ?? 0, data[i + 2] ?? 0)) data[i + 3] = 0;
  }
  ctx.putImageData(frame, 0, 0);
  keyed.set(key, canvas);
  return canvas;
}

export type Spot = {
  x: number;
  y: number;
  scale: number;
  mouthX: number;
  mouthY: number;
  mouthScale: number;
};

export type HitBox = {
  id: string;
  kind: "person" | "mouth" | "background";
  role: "body" | "handle";
  x: number;
  y: number;
  w: number;
  h: number;
};

export function defaultSpot(index: number, count: number, person: ScenePerson): Spot {
  return {
    x: ((index + 0.5) / Math.max(1, count)) * 100,
    y: 56,
    scale: 70,
    mouthX: person.mouthX,
    mouthY: person.mouthY,
    mouthScale: person.mouthScale,
  };
}

function strokeBox(
  ctx: CanvasRenderingContext2D,
  box: { x: number; y: number; w: number; h: number },
  id: string,
  kind: HitBox["kind"],
  boxes: HitBox[],
) {
  ctx.save();
  ctx.strokeStyle = "#1c2420";
  ctx.lineWidth = 3;
  ctx.setLineDash([10, 7]);
  ctx.strokeRect(box.x, box.y, box.w, box.h);
  ctx.setLineDash([]);
  const size = 22;
  const handle = {
    id,
    kind,
    role: "handle" as const,
    x: box.x + box.w - size / 2,
    y: box.y + box.h - size / 2,
    w: size,
    h: size,
  };
  ctx.fillStyle = "#c45c26";
  ctx.fillRect(handle.x, handle.y, handle.w, handle.h);
  ctx.restore();
  boxes.push(handle);
}

export function paintTable(
  ctx: CanvasRenderingContext2D,
  background: HTMLImageElement,
  table: HTMLImageElement,
  people: {
    person: ScenePerson;
    body: HTMLImageElement;
    mouth: HTMLImageElement;
    shape: MouthName;
    spot: Spot;
  }[],
  room: { x: number; y: number; scale: number },
  selected: { id: string; kind: HitBox["kind"] } | null,
): HitBox[] {
  const w = ctx.canvas.width;
  const h = ctx.canvas.height;
  const boxes: HitBox[] = [];
  const cover = Math.max(w / background.width, h / background.height) * (room.scale / 100);
  const bw = background.width * cover;
  const bh = background.height * cover;
  ctx.drawImage(background, (room.x / 100) * w - bw / 2, (room.y / 100) * h - bh / 2, bw, bh);

  const placed = people.map((entry) => {
    const bodyH = (entry.spot.scale / 100) * h;
    const fit = bodyH / Math.max(1, entry.body.height);
    const dw = entry.body.width * fit;
    const dh = bodyH;
    const dx = (entry.spot.x / 100) * w - dw / 2;
    const dy = (entry.spot.y / 100) * h - dh / 2;
    return { entry, dx, dy, dw, dh };
  });

  for (const item of placed) {
    ctx.drawImage(
      keyedImage(item.entry.body, Math.round(item.dw), Math.round(item.dh)),
      item.dx,
      item.dy,
      item.dw,
      item.dh,
    );
    boxes.push({
      id: item.entry.person.id,
      kind: "person",
      role: "body",
      x: item.dx,
      y: item.dy,
      w: item.dw,
      h: item.dh,
    });
    const jaw = JAW[item.entry.shape];
    const mw = (item.entry.spot.mouthScale / 100) * item.dw;
    const mh = item.entry.mouth.width ? (item.entry.mouth.height / item.entry.mouth.width) * mw * jaw : mw * jaw;
    const mx = item.dx + (item.entry.spot.mouthX / 100) * item.dw - mw / 2;
    const my = item.dy + (item.entry.spot.mouthY / 100) * item.dh;
    ctx.drawImage(item.entry.mouth, mx, my, mw, mh);
    boxes.push({
      id: item.entry.person.id,
      kind: "mouth",
      role: "body",
      x: mx,
      y: my,
      w: mw,
      h: mh,
    });
  }

  const tableH = h * 0.4;
  const tableW = w * 1.04;
  ctx.drawImage(
    keyedImage(table, Math.round(tableW), Math.round(tableH)),
    (w - tableW) / 2,
    h - tableH * 0.92,
    tableW,
    tableH,
  );

  if (selected?.kind === "background") {
    strokeBox(ctx, { x: 12, y: 12, w: w - 24, h: h - 24 }, "background", "background", boxes);
  }
  for (const item of placed) {
    if (selected?.id === item.entry.person.id && selected.kind === "person") {
      strokeBox(ctx, { x: item.dx, y: item.dy, w: item.dw, h: item.dh }, item.entry.person.id, "person", boxes);
    }
    if (selected?.id === item.entry.person.id && selected.kind === "mouth") {
      const mouth = boxes.find((box) => box.id === item.entry.person.id && box.kind === "mouth");
      if (mouth) strokeBox(ctx, mouth, item.entry.person.id, "mouth", boxes);
    }
  }
  return boxes;
}
