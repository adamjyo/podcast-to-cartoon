export const MOUTH_NAMES = ["closed", "small", "medium", "wide", "round", "teeth"] as const;

export type MouthName = (typeof MOUTH_NAMES)[number];

export const STOCK_MOUTHS: Record<MouthName, string> = {
  closed: "/mouths/closed.png",
  small: "/mouths/small.png",
  medium: "/mouths/medium.png",
  wide: "/mouths/wide.png",
  round: "/mouths/round.png",
  teeth: "/mouths/teeth.png",
};

export const TALK_ORDER: MouthName[] = [
  "closed",
  "small",
  "medium",
  "wide",
  "medium",
  "round",
  "teeth",
  "small",
];

/** How far the jaw opens. 1 is the drawn mouth; closed is shorter. */
export const JAW: Record<MouthName, number> = {
  closed: 0.62,
  small: 0.82,
  medium: 1,
  wide: 1.22,
  round: 1.08,
  teeth: 1.14,
};

export type SpeechBeat = { shape: MouthName; ms: number };

/** Uneven holds: quick consonants, longer vowels, real pauses. */
export const SPEECH_LINE: SpeechBeat[] = [
  { shape: "closed", ms: 120 },
  { shape: "small", ms: 70 },
  { shape: "medium", ms: 140 },
  { shape: "small", ms: 55 },
  { shape: "teeth", ms: 75 },
  { shape: "medium", ms: 150 },
  { shape: "wide", ms: 110 },
  { shape: "medium", ms: 90 },
  { shape: "small", ms: 60 },
  { shape: "closed", ms: 180 },
  { shape: "round", ms: 130 },
  { shape: "small", ms: 50 },
  { shape: "medium", ms: 140 },
  { shape: "teeth", ms: 70 },
  { shape: "wide", ms: 100 },
  { shape: "medium", ms: 120 },
  { shape: "small", ms: 65 },
  { shape: "closed", ms: 200 },
  { shape: "medium", ms: 130 },
  { shape: "small", ms: 55 },
  { shape: "wide", ms: 90 },
  { shape: "teeth", ms: 60 },
  { shape: "small", ms: 70 },
  { shape: "closed", ms: 220 },
];

export function speechLine(repeats = 2): SpeechBeat[] {
  const beats: SpeechBeat[] = [];
  for (let i = 0; i < repeats; i += 1) beats.push(...SPEECH_LINE);
  return beats;
}

export function splitMouthSheet(src: string): Promise<Record<MouthName, string>> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const cols = 3;
      const rows = 2;
      const out = {} as Record<MouthName, string>;
      MOUTH_NAMES.forEach((name, i) => {
        const c = i % cols;
        const r = Math.floor(i / cols);
        const x0 = Math.round((c * img.width) / cols);
        const x1 = Math.round(((c + 1) * img.width) / cols);
        const y0 = Math.round((r * img.height) / rows);
        const y1 = Math.round(((r + 1) * img.height) / rows);
        const w = x1 - x0;
        const h = y1 - y0;
        const canvas = document.createElement("canvas");
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        ctx.drawImage(img, x0, y0, w, h, 0, 0, w, h);
        const frame = ctx.getImageData(0, 0, w, h);
        const d = frame.data;
        for (let p = 0; p < d.length; p += 4) {
          const R = d[p] ?? 0;
          const G = d[p + 1] ?? 0;
          const B = d[p + 2] ?? 0;
          if (R > 170 && B > 150 && G < 140 && R - G > 40 && B - G > 30) {
            d[p + 3] = 0;
          }
        }
        ctx.putImageData(frame, 0, 0);
        out[name] = canvas.toDataURL("image/png");
      });
      resolve(out);
    };
    img.onerror = () => reject(new Error("Could not read the mouth sheet."));
    img.src = src;
  });
}

export function shrinkPhoto(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Could not read that photo."));
    reader.onload = () => {
      const img = new Image();
      img.onload = () => {
        const max = 768;
        const scale = Math.min(1, max / Math.max(img.width, img.height));
        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round(img.width * scale));
        canvas.height = Math.max(1, Math.round(img.height * scale));
        const ctx = canvas.getContext("2d");
        if (!ctx) {
          reject(new Error("Could not prepare that photo."));
          return;
        }
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        resolve(canvas.toDataURL("image/jpeg", 0.82));
      };
      img.onerror = () => reject(new Error("That file is not a photo."));
      img.src = String(reader.result);
    };
    reader.readAsDataURL(file);
  });
}
