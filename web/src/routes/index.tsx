import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { drawAvatar, drawMouths } from "@/lib/draw";
import { forgetAvatar, keepAvatar, listAvatars, type SavedAvatar } from "@/lib/library";
import {
  JAW,
  MOUTH_NAMES,
  STOCK_MOUTHS,
  speechLine,
  shrinkPhoto,
  splitMouthSheet,
  type MouthName,
} from "@/lib/mouths";

export const Route = createFileRoute("/")({ component: Studio });

type Seat = {
  id: string;
  libraryId?: string;
  name: string;
  note: string;
  photo: string;
  avatar?: string;
  mouths?: Partial<Record<MouthName, string>>;
  error?: string;
  busy?: "avatar" | "mouths";
  kept?: boolean;
  mouthX: number;
  mouthY: number;
  mouthScale: number;
};

const MOUTH_SHAPES = ["closed", "small", "medium", "wide", "round", "teeth"] as const;

const MOUTH_PEOPLE = [
  { id: "adam", label: "Adam" },
  { id: "ben", label: "Ben" },
  { id: "corey", label: "Corey" },
  { id: "emily", label: "Emily" },
  { id: "abby-r", label: "Abby R" },
  { id: "abby-s", label: "Abby S" },
];

const TABLE_LAYERS = [
  { href: "/cast/layers/adam.png", file: "adam.png", label: "Adam" },
  { href: "/cast/layers/ben.png", file: "ben.png", label: "Ben" },
  { href: "/cast/layers/corey.png", file: "corey.png", label: "Corey" },
  { href: "/cast/layers/emily.png", file: "emily.png", label: "Emily" },
  { href: "/cast/layers/abby-r.png", file: "abby-r.png", label: "Abby R" },
  { href: "/cast/layers/abby-s.png", file: "abby-s.png", label: "Abby S" },
  { href: "/cast/layers/table.png", file: "table.png", label: "Table" },
];

const LINEUP_MOUTHS = [
  { href: "/cast/lineup/adam-mouths.png", file: "adam-mouths.png", label: "Adam mouths" },
  { href: "/cast/lineup/ben-mouths.png", file: "ben-mouths.png", label: "Ben mouths" },
  { href: "/cast/lineup/corey-mouths.png", file: "corey-mouths.png", label: "Corey mouths" },
  { href: "/cast/lineup/emily-mouths.png", file: "emily-mouths.png", label: "Emily mouths" },
  { href: "/cast/lineup/abby-r-mouths.png", file: "abby-r-mouths.png", label: "Abby R mouths" },
  { href: "/cast/lineup/abby-s-mouths.png", file: "abby-s-mouths.png", label: "Abby S mouths" },
];

const LINEUP = [
  { href: "/cast/lineup/adam.png", file: "adam.png", label: "Adam" },
  { href: "/cast/lineup/ben.png", file: "ben.png", label: "Ben" },
  { href: "/cast/lineup/corey.png", file: "corey.png", label: "Corey" },
  { href: "/cast/lineup/emily.png", file: "emily.png", label: "Emily" },
  { href: "/cast/lineup/abby-r.png", file: "abby-r.png", label: "Abby R" },
  { href: "/cast/lineup/abby-s.png", file: "abby-s.png", label: "Abby S" },
  { href: "/cast/lineup/table.png", file: "table.png", label: "Table" },
];

const CAST = [
  {
    name: "Adam P",
    sheets: [
      { href: "/cast/adam-p-avatar.png", file: "adam-p-avatar.png", label: "Portrait" },
      { href: "/cast/adam-p-full-body.png", file: "adam-p-full-body.png", label: "Full body" },
      { href: "/cast/adam-p-mouths.png", file: "adam-p-mouths.png", label: "Mouths" },
    ],
  },
  {
    name: "Ben",
    sheets: [
      { href: "/cast/ben-portrait.png?v=2", file: "ben-portrait.png", label: "Portrait" },
      { href: "/cast/ben-standing.png?v=2", file: "ben-standing.png", label: "Standing" },
      { href: "/cast/ben-mouths.png?v=2", file: "ben-mouths.png", label: "Mouths" },
      { href: "/cast/ben-sitting.png?v=2", file: "ben-sitting.png", label: "Sitting" },
      { href: "/cast/ben-at-table.png?v=2", file: "ben-at-table.png", label: "At the table" },
    ],
  },
  {
    name: "Corey",
    sheets: [
      { href: "/cast/corey-portrait.png", file: "corey-portrait.png", label: "Portrait" },
      { href: "/cast/corey-full-body.png", file: "corey-full-body.png", label: "Full body" },
      { href: "/cast/corey-mouths.png", file: "corey-mouths.png", label: "Mouths" },
      { href: "/cast/corey-sitting.png", file: "corey-sitting.png", label: "Sitting" },
    ],
  },
  {
    name: "Emily",
    sheets: [
      { href: "/cast/emily-portrait.png", file: "emily-portrait.png", label: "Portrait" },
      { href: "/cast/emily-full-body.png", file: "emily-full-body.png", label: "Full body" },
      { href: "/cast/emily-mouths.png", file: "emily-mouths.png", label: "Mouths" },
      { href: "/cast/emily-sitting.png", file: "emily-sitting.png", label: "Sitting" },
    ],
  },
  {
    name: "Abby R",
    sheets: [
      { href: "/cast/abby-r-portrait.png", file: "abby-r-portrait.png", label: "Portrait" },
      { href: "/cast/abby-r-full-body.png", file: "abby-r-full-body.png", label: "Full body" },
      { href: "/cast/abby-r-mouths.png", file: "abby-r-mouths.png", label: "Mouths" },
      { href: "/cast/abby-r-sitting.png", file: "abby-r-sitting.png", label: "Sitting" },
    ],
  },
  {
    name: "Abby S",
    sheets: [
      { href: "/cast/abby-s-portrait.png", file: "abby-s-portrait.png", label: "Portrait" },
      { href: "/cast/abby-s-full-body.png", file: "abby-s-full-body.png", label: "Full body" },
      { href: "/cast/abby-s-mouths.png", file: "abby-s-mouths.png", label: "Mouths" },
      { href: "/cast/abby-s-sitting.png", file: "abby-s-sitting.png", label: "Sitting" },
    ],
  },
];

function Studio() {
  const [seats, setSeats] = useState<Seat[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [shape, setShape] = useState<MouthName>("closed");
  const [talking, setTalking] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportNote, setExportNote] = useState<string | null>(null);
  const [library, setLibrary] = useState<SavedAvatar[]>([]);
  const [libraryError, setLibraryError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const talkTimer = useRef(0);

  const seat = seats.find((s) => s.id === active) ?? seats[0];

  useEffect(() => {
    void listAvatars()
      .then(setLibrary)
      .catch(() => setLibraryError("Saved avatars are unavailable in this browser."));
  }, []);

  useEffect(() => {
    if (!talking) return;
    const beats = speechLine(2);
    let i = 0;
    let cancelled = false;
    const step = () => {
      if (cancelled) return;
      const beat = beats[i];
      if (!beat) {
        setShape("closed");
        setTalking(false);
        return;
      }
      setShape(beat.shape);
      i += 1;
      talkTimer.current = window.setTimeout(step, beat.ms);
    };
    step();
    return () => {
      cancelled = true;
      window.clearTimeout(talkTimer.current);
    };
  }, [talking]);

  async function onFiles(list: FileList | null) {
    if (!list?.length) return;
    const room = 5 - seats.length;
    const files = Array.from(list).slice(0, room);
    const next: Seat[] = [];
    for (const file of files) {
      if (!file.type.startsWith("image/")) continue;
      const photo = await shrinkPhoto(file);
      next.push({
        id: crypto.randomUUID(),
        name: file.name.replace(/\.[^.]+$/, "").replace(/[-_]/g, " "),
        note: "",
        photo,
        mouthX: 50,
        mouthY: 42,
        mouthScale: 16,
      });
    }
    setSeats((prev) => [...prev, ...next].slice(0, 5));
    setActive((current) => current ?? next[0]?.id ?? null);
  }

  function patch(id: string, partial: Partial<Seat>) {
    setSeats((prev) => prev.map((s) => (s.id === id ? { ...s, ...partial } : s)));
  }

  async function develop(id: string) {
    const current = seats.find((s) => s.id === id);
    if (!current || current.busy) return;
    patch(id, { busy: "avatar", error: undefined });
    const result = await drawAvatar({
      data: { imageDataUrl: current.photo, note: current.note },
    });
    if (!result.ok) {
      patch(id, { busy: undefined, error: result.error });
      return;
    }
    patch(id, { busy: undefined, avatar: result.image, kept: false, error: undefined });
    setActive(id);
  }

  async function cutMouths(id: string) {
    const current = seats.find((s) => s.id === id);
    if (!current?.avatar || current.busy) return;
    patch(id, { busy: "mouths", error: undefined });
    const result = await drawMouths({ data: { imageDataUrl: current.avatar } });
    if (!result.ok) {
      patch(id, { busy: undefined, error: result.error });
      return;
    }
    try {
      const mouths = await splitMouthSheet(result.image);
      patch(id, { busy: undefined, mouths, kept: false, error: undefined });
    } catch (err) {
      patch(id, {
        busy: undefined,
        error: err instanceof Error ? err.message : "Could not cut the mouths.",
      });
    }
  }

  async function keep(id: string) {
    const current = seats.find((s) => s.id === id);
    if (!current?.avatar) return;
    const libraryId = current.libraryId ?? crypto.randomUUID();
    try {
      await keepAvatar({
        id: libraryId,
        name: current.name || "Unnamed",
        note: current.note,
        photo: current.photo,
        avatar: current.avatar,
        mouths: current.mouths,
        mouthX: current.mouthX,
        mouthY: current.mouthY,
        mouthScale: current.mouthScale,
        savedAt: Date.now(),
      });
      patch(id, { libraryId, kept: true, error: undefined });
      setLibrary(await listAvatars());
    } catch (err) {
      patch(id, {
        error: err instanceof Error ? err.message : "Could not save that avatar.",
      });
    }
  }

  function loadImage(src: string) {
    return new Promise<HTMLImageElement>((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("Could not load a picture for the video."));
      img.src = src;
    });
  }

  function paintFrame(
    ctx: CanvasRenderingContext2D,
    avatar: HTMLImageElement,
    mouth: HTMLImageElement,
    place: { mouthX: number; mouthY: number; mouthScale: number },
    shapeName: MouthName,
  ) {
    const w = ctx.canvas.width;
    const h = ctx.canvas.height;
    ctx.fillStyle = "#f3ecdf";
    ctx.fillRect(0, 0, w, h);
    const cover = Math.max(w / avatar.width, h / avatar.height);
    const dw = avatar.width * cover;
    const dh = avatar.height * cover;
    const jaw = JAW[shapeName];
    const bob = (jaw - 1) * 6;
    ctx.drawImage(avatar, (w - dw) / 2, (h - dh) / 2 + bob, dw, dh);
    const mw = (place.mouthScale / 100) * w;
    const mh = mouth.width ? (mouth.height / mouth.width) * mw * jaw : mw * jaw;
    const x = (place.mouthX / 100) * w - mw / 2;
    const y = (place.mouthY / 100) * h;
    ctx.drawImage(mouth, x, y, mw, mh);
  }

  async function exportVideo() {
    const face = seat?.avatar ?? seat?.photo ?? "/cast/lineup/adam.png";
    const mouths = seat?.mouths ?? {
      closed: "/cast/mouth-parts/adam/closed.png",
      small: "/cast/mouth-parts/adam/small.png",
      medium: "/cast/mouth-parts/adam/medium.png",
      wide: "/cast/mouth-parts/adam/wide.png",
      round: "/cast/mouth-parts/adam/round.png",
      teeth: "/cast/mouth-parts/adam/teeth.png",
    };
    const place = seat
      ? { mouthX: seat.mouthX, mouthY: seat.mouthY, mouthScale: seat.mouthScale }
      : { mouthX: 50, mouthY: 43, mouthScale: 16 };
    const mime = ["video/webm;codecs=vp9", "video/webm", "video/mp4"].find((type) =>
      typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(type),
    );
    if (!mime) {
      setExportNote("This browser cannot record a video.");
      return;
    }
    setExporting(true);
    setExportNote("Drawing the line…");
    setTalking(false);
    try {
      const avatar = await loadImage(face);
      const mouthImgs = {} as Record<MouthName, HTMLImageElement>;
      for (const name of MOUTH_NAMES) mouthImgs[name] = await loadImage(mouths[name] ?? STOCK_MOUTHS[name]);
      const canvas = document.createElement("canvas");
      canvas.width = 720;
      canvas.height = 960;
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("Could not start the video.");
      const stream = canvas.captureStream(24);
      paintFrame(ctx, avatar, mouthImgs.closed, place, "closed");
      const rec = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 2_500_000 });
      const chunks: Blob[] = [];
      rec.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data);
      };
      const stopped = new Promise<void>((resolve) => {
        rec.onstop = () => resolve();
      });
      rec.start();
      const beats = speechLine(2);
      for (let i = 0; i < beats.length; i += 1) {
        const beat = beats[i];
        if (!beat) continue;
        setShape(beat.shape);
        paintFrame(ctx, avatar, mouthImgs[beat.shape], place, beat.shape);
        setExportNote(`Exporting… ${Math.round(((i + 1) / beats.length) * 100)}%`);
        await new Promise((resolve) => window.setTimeout(resolve, beat.ms));
      }
      paintFrame(ctx, avatar, mouthImgs.closed, place, "closed");
      await new Promise((resolve) => window.setTimeout(resolve, 80));
      rec.stop();
      await stopped;
      const blob = new Blob(chunks, { type: mime });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${(seat?.name || "paper-mic").replace(/\s+/g, "-").toLowerCase()}.${mime.includes("mp4") ? "mp4" : "webm"}`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 4000);
      setShape("closed");
      setExportNote("Video downloaded.");
    } catch (err) {
      setExportNote(err instanceof Error ? err.message : "Could not export the video.");
    } finally {
      setExporting(false);
    }
  }

  function reuse(saved: SavedAvatar) {
    const existing = seats.find((s) => s.libraryId === saved.id);
    if (existing) {
      setActive(existing.id);
      return;
    }
    if (seats.length >= 5) return;
    const next: Seat = {
      id: crypto.randomUUID(),
      libraryId: saved.id,
      name: saved.name,
      note: saved.note,
      photo: saved.photo,
      avatar: saved.avatar,
      mouths: saved.mouths,
      kept: true,
      mouthX: saved.mouthX,
      mouthY: saved.mouthY,
      mouthScale: saved.mouthScale,
    };
    setSeats((prev) => [...prev, next]);
    setActive(next.id);
  }

  async function forget(id: string) {
    await forgetAvatar(id);
    setLibrary(await listAvatars());
    setSeats((prev) => prev.map((s) => (s.libraryId === id ? { ...s, kept: false, libraryId: undefined } : s)));
  }

  const mouths = seat?.mouths ?? STOCK_MOUTHS;
  const mouthSrc = mouths[shape] ?? STOCK_MOUTHS[shape];

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-4 py-8 pb-28 sm:px-6">
      <a
        href="/distrokid-daily-streams.csv"
        download="distrokid-daily-streams.csv"
        className="mb-8 flex flex-col gap-3 rounded-2xl border border-line bg-cream px-5 py-4 sm:flex-row sm:items-center sm:justify-between"
      >
        <span>
          <span className="block font-display text-2xl text-ink">Daily streams</span>
          <span className="text-sm text-muted">16 Oct 2025 through 14 Oct 2026. 364 days.</span>
        </span>
        <span className="inline-flex h-12 items-center justify-center rounded-full bg-sienna px-5 font-medium text-cream">
          Download CSV
        </span>
      </a>
      <header className="mb-8 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-medium tracking-wide text-sienna">Paper Mic</p>
          <h1 className="font-display text-4xl text-balance text-ink sm:text-5xl">
            Load headshots. Draw the cast.
          </h1>
          <p className="mt-2 max-w-xl text-pretty text-muted">
            Drop a photo of each person. Paper Mic redraws them as an ink-and-watercolor avatar,
            then cuts the six mouth shapes the cartoon needs to talk.
          </p>
        </div>
        <button
          type="button"
          className="h-12 rounded-full bg-sienna px-5 font-medium text-cream disabled:opacity-40"
          onClick={() => inputRef.current?.click()}
          disabled={seats.length >= 5}
        >
          {seats.length ? "Add another headshot" : "Load headshots"}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          multiple
          className="sr-only"
          onChange={(e) => {
            void onFiles(e.target.files);
            e.target.value = "";
          }}
        />
      </header>

      <section className="mb-8">
        <h2 className="font-display text-2xl text-ink">Mouth parts</h2>
        <p className="mt-1 max-w-xl text-sm text-muted">
          Drawn for these faces. Each shape is its own picture with a transparent background. Download the six for a person, then set them as that person’s mouth.
        </p>
        <div className="mt-4 flex flex-col gap-6">
          {MOUTH_PEOPLE.map((person) => (
            <div key={person.id}>
              <h3 className="font-display text-xl text-ink">{person.label}</h3>
              <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                {MOUTH_SHAPES.map((shape) => (
                  <article key={shape} className="overflow-hidden rounded-2xl border border-line bg-cream">
                    <img loading="lazy"
                      src={`/cast/mouth-parts/${person.id}/${shape}.png?v=3`}
                      alt={`${person.label} ${shape} mouth`}
                      className="aspect-[4/3] w-full cutout object-contain"
                    />
                    <a
                      href={`/cast/mouth-parts/${person.id}/${shape}.png?v=3`}
                      download={`${person.id}-${shape}.png`}
                      target="_blank"
                      rel="noopener"
                      className="flex h-11 items-center justify-center text-sm font-medium text-sienna"
                    >
                      {shape}
                    </a>
                  </article>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="mb-8">
        <h2 className="font-display text-2xl text-ink">Backgrounds</h2>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          {[
            { href: "/backgrounds/coffee-shop.jpg?v=2", file: "coffee-shop.jpg", label: "Coffee shop" },
            { href: "/backgrounds/library.jpg?v=2", file: "library.jpg", label: "Library" },
          ].map((item) => (
            <article key={item.href} className="overflow-hidden rounded-3xl border border-line bg-cream">
              <img loading="lazy" src={item.href} alt={item.label} className="aspect-video w-full object-cover" />
              <div className="flex items-center justify-between gap-3 p-3">
                <span className="text-sm font-medium text-ink">{item.label}</span>
                <a href={item.href} download={item.file} target="_blank" rel="noopener" className="inline-flex h-11 items-center rounded-full bg-sienna px-4 text-sm font-medium text-cream">
                  Download
                </a>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="mb-8">
        <h2 className="font-display text-2xl text-ink">At the table</h2>
        <p className="mt-1 text-sm text-muted">Adam is with them. Each person and the table is its own layer.</p>
        <article className="mt-3 overflow-hidden rounded-3xl border border-line bg-cream">
          <img loading="lazy"
            src="/cast/cast-at-the-table.png?v=6"
            alt="Adam, Ben, Corey, Emily, Abby R, and Abby S sitting behind one table"
            className="aspect-video w-full cutout object-contain"
          />
          <div className="flex items-center justify-between gap-3 p-3">
            <span className="text-sm font-medium text-ink">All six, stacked</span>
            <a
              href="/cast/cast-at-the-table.png?v=6"
              download="cast-at-the-table.png"
              target="_blank"
              rel="noopener"
              className="inline-flex h-11 items-center rounded-full bg-sienna px-4 text-sm font-medium text-cream"
            >
              Download
            </a>
          </div>
        </article>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
          {TABLE_LAYERS.map((layer) => (
            <article key={layer.href} className="overflow-hidden rounded-2xl border border-line bg-cream">
              <img loading="lazy" src={layer.href} alt={layer.label} className="aspect-square w-full cutout object-contain" />
              <a
                href={layer.href}
                download={layer.file}
                target="_blank"
                rel="noopener"
                className="flex h-11 items-center justify-center text-sm font-medium text-sienna"
              >
                {layer.label}
              </a>
            </article>
          ))}
        </div>
      </section>

      <section className="mb-8">
        <h2 className="font-display text-2xl text-ink">Lined up</h2>
        <p className="mt-1 text-sm text-muted">Each person from the group shot, same size, ready to sit behind the table.</p>
        <article className="mt-3 overflow-hidden rounded-3xl border border-line bg-cream">
          <img loading="lazy" src="/cast/lineup/lined-up.png" alt="The cast lined up behind one table" className="aspect-video w-full cutout object-contain" />
          <div className="flex items-center justify-between gap-3 p-3">
            <span className="text-sm font-medium text-ink">All six in a line</span>
            <a href="/cast/lineup/lined-up.png" download="lined-up.png" target="_blank" rel="noopener" className="inline-flex h-11 items-center rounded-full bg-sienna px-4 text-sm font-medium text-cream">
              Download
            </a>
          </div>
        </article>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
          {LINEUP.map((item) => (
            <article key={item.href} className="overflow-hidden rounded-2xl border border-line bg-cream">
              <img loading="lazy" src={item.href} alt={item.label} className="aspect-[3/4] w-full cutout object-contain" />
              <a href={item.href} download={item.file} target="_blank" rel="noopener" className="flex h-11 items-center justify-center text-sm font-medium text-sienna">
                {item.label}
              </a>
            </article>
          ))}
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {LINEUP_MOUTHS.map((item) => (
            <article key={item.href} className="overflow-hidden rounded-2xl border border-line bg-cream">
              <img loading="lazy" src={item.href} alt={item.label} className="aspect-[3/2] w-full cutout object-contain" />
              <a href={item.href} download={item.file} target="_blank" rel="noopener" className="flex h-11 items-center justify-center text-sm font-medium text-sienna">
                {item.label}
              </a>
            </article>
          ))}
        </div>
      </section>

      <section className="mb-8 flex flex-col gap-8">
        {CAST.map((person) => (
          <div key={person.name}>
            <h2 className="font-display text-2xl text-ink">{person.name}</h2>
            <div className="mt-3 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {person.sheets.map((sheet) => (
                <article key={sheet.href} className="overflow-hidden rounded-3xl border border-line bg-cream">
                  <img loading="lazy"
                    src={sheet.href}
                    alt={`${person.name} ${sheet.label}`}
                    className="aspect-[3/4] w-full cutout object-contain"
                  />
                  <div className="flex items-center justify-between gap-3 p-3">
                    <span className="text-sm font-medium text-ink">{sheet.label}</span>
                    <a
                      href={sheet.href}
                      download={sheet.file}
                      target="_blank"
                      rel="noopener"
                      className="inline-flex h-11 items-center rounded-full bg-sienna px-4 text-sm font-medium text-cream"
                    >
                      Download
                    </a>
                  </div>
                </article>
              ))}
            </div>
          </div>
        ))}
      </section>

      {seats.length === 0 ? (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="flex min-h-72 w-full flex-col items-center justify-center rounded-3xl border border-dashed border-line bg-cream px-6 text-center"
        >
          <span className="font-display text-2xl text-ink">Drop photos here</span>
          <span className="mt-2 max-w-sm text-muted">
            Up to five people. A clear face, looking at the camera, works best.
          </span>
        </button>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <section className="rounded-3xl border border-line bg-cream p-4 sm:p-6">
            {seat?.avatar ? (
              <div className="relative mx-auto aspect-portrait w-full max-w-md overflow-hidden rounded-2xl bg-paper">
                <img loading="lazy" src={seat.avatar} alt="" className="h-full w-full object-cover" />
                <img loading="lazy"
                  src={mouthSrc}
                  alt=""
                  className="pointer-events-none absolute -translate-x-1/2"
                  style={{
                    left: `${seat.mouthX}%`,
                    top: `${seat.mouthY}%`,
                    width: `${seat.mouthScale}%`,
                    transformOrigin: "center 18%",
                    transform: `translateX(-50%) scaleY(${talking || exporting ? JAW[shape] : 1})`,
                  }}
                />
              </div>
            ) : (
              <div className="relative mx-auto aspect-portrait w-full max-w-md overflow-hidden rounded-2xl bg-paper">
                <img loading="lazy"
                  src={seat?.photo}
                  alt=""
                  className="h-full w-full object-cover grayscale-[0.2]"
                />
                <p className="absolute inset-x-0 bottom-0 bg-ink/80 px-4 py-3 text-center text-cream">
                  Headshot loaded. Draw the avatar to start.
                </p>
              </div>
            )}

            <div className="mt-4 flex flex-wrap items-center gap-3">
              <button
                type="button"
                className="h-11 rounded-full bg-ink px-4 text-cream disabled:opacity-40"
                disabled={!seat || talking || exporting}
                onClick={() => setTalking(true)}
              >
                Play a line
              </button>
              <button
                type="button"
                className="h-11 rounded-full bg-sienna px-4 font-medium text-cream disabled:opacity-40"
                disabled={exporting}
                onClick={() => void exportVideo()}
              >
                {exporting ? "Exporting…" : "Export video"}
              </button>
              <div className="flex gap-2">
                {MOUTH_NAMES.map((name) => (
                  <button
                    key={name}
                    type="button"
                    aria-label={name}
                    onClick={() => {
                      setTalking(false);
                      setShape(name);
                    }}
                    className={`h-11 w-11 overflow-hidden rounded-full border ${
                      shape === name ? "border-sienna" : "border-line"
                    } bg-paper`}
                  >
                    <img loading="lazy" src={(seat?.mouths ?? STOCK_MOUTHS)[name]} alt="" className="h-full w-full object-contain" />
                  </button>
                ))}
              </div>
            </div>

            {seat?.avatar && (
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <label className="text-sm text-muted">
                  Mouth sideways
                  <input
                    type="range"
                    min={30}
                    max={70}
                    value={seat.mouthX}
                    onChange={(e) => patch(seat.id, { mouthX: Number(e.target.value) })}
                    className="mt-1 w-full"
                  />
                </label>
                <label className="text-sm text-muted">
                  Mouth height
                  <input
                    type="range"
                    min={20}
                    max={80}
                    value={seat.mouthY}
                    onChange={(e) => patch(seat.id, { mouthY: Number(e.target.value) })}
                    className="mt-1 w-full"
                  />
                </label>
                <label className="text-sm text-muted">
                  Mouth size
                  <input
                    type="range"
                    min={8}
                    max={40}
                    value={seat.mouthScale}
                    onChange={(e) => patch(seat.id, { mouthScale: Number(e.target.value) })}
                    className="mt-1 w-full"
                  />
                </label>
              </div>
            )}
          </section>

          <aside className="flex flex-col gap-3">
            {seats.map((item) => (
              <article
                key={item.id}
                className={`rounded-2xl border bg-cream p-3 ${
                  item.id === seat?.id ? "border-sienna" : "border-line"
                }`}
              >
                <button type="button" className="flex w-full gap-3 text-left" onClick={() => setActive(item.id)}>
                  <img loading="lazy" src={item.avatar ?? item.photo} alt="" className="h-16 w-14 rounded-xl object-cover" />
                  <span className="min-w-0 flex-1">
                    <input
                      value={item.name}
                      onChange={(e) => patch(item.id, { name: e.target.value })}
                      onClick={(e) => e.stopPropagation()}
                      className="w-full bg-transparent font-medium text-ink outline-none"
                      aria-label="Name"
                    />
                    <span className="block text-sm text-muted">
                      {item.busy === "avatar"
                        ? "Drawing…"
                        : item.busy === "mouths"
                          ? "Cutting mouths…"
                          : item.avatar
                            ? "Avatar ready"
                            : "Headshot ready"}
                    </span>
                  </span>
                </button>
                <input
                  value={item.note}
                  onChange={(e) => patch(item.id, { note: e.target.value })}
                  placeholder="Keep the glasses, warmer coat…"
                  className="mt-2 h-10 w-full rounded-xl border border-line bg-paper px-3 text-sm outline-none"
                />
                <div className="mt-2 flex gap-2">
                  <button
                    type="button"
                    disabled={!!item.busy}
                    onClick={() => void develop(item.id)}
                    className="h-11 flex-1 rounded-full bg-sienna text-sm font-medium text-cream disabled:opacity-40"
                  >
                    Draw avatar
                  </button>
                  <button
                    type="button"
                    disabled={!item.avatar || !!item.busy}
                    onClick={() => void cutMouths(item.id)}
                    className="h-11 flex-1 rounded-full border border-line text-sm font-medium disabled:opacity-40"
                  >
                    Cut mouths
                  </button>
                </div>
                {item.avatar && (
                  <div className="mt-2 flex items-center gap-4">
                    <button
                      type="button"
                      onClick={() => void keep(item.id)}
                      className="h-11 text-sm font-medium text-sienna"
                    >
                      {item.kept ? "Update saved copy" : "Keep avatar"}
                    </button>
                    <a
                      href={item.avatar}
                      download={`${item.name || "avatar"}.jpg`}
                      className="inline-flex h-11 items-center text-sm text-muted"
                    >
                      Download
                    </a>
                  </div>
                )}
                {item.error && <p className="mt-2 text-sm text-sienna">{item.error}</p>}
              </article>
            ))}
            <p className="px-1 text-sm text-pretty text-muted">
              Mouth buttons use a shared ink kit until you cut a set from that avatar. Place the mouth with the sliders, then play a line. Kept avatars stay in this browser.
            </p>
          </aside>
        </div>
      )}
      {(library.length > 0 || libraryError) && (
        <section className="mt-8">
          <h2 className="font-display text-2xl text-ink">Saved cast</h2>
          {libraryError && <p className="mt-2 text-sm text-sienna">{libraryError}</p>}
          <div className="mt-3 flex gap-3 overflow-x-auto pb-2">
            {library.map((item) => (
              <article key={item.id} className="w-36 shrink-0 rounded-2xl border border-line bg-cream p-2">
                <button type="button" className="w-full text-left" onClick={() => reuse(item)}>
                  <img loading="lazy" src={item.avatar} alt="" className="aspect-portrait w-full rounded-xl object-cover" />
                  <span className="mt-2 block truncate text-sm font-medium text-ink">{item.name}</span>
                </button>
                <button
                  type="button"
                  className="mt-1 h-11 text-sm text-muted"
                  onClick={() => void forget(item.id)}
                >
                  Remove
                </button>
              </article>
            ))}
          </div>
        </section>
      )}
      <div className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-paper/95 px-4 py-3">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-muted">
            {exportNote ?? "Scroll for the rest of the cast. Export records the face talking."}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              className="h-11 rounded-full bg-ink px-4 text-sm text-cream disabled:opacity-40"
              disabled={talking || exporting}
              onClick={() => setTalking(true)}
            >
              Play a line
            </button>
            <button
              type="button"
              className="h-11 rounded-full bg-sienna px-4 text-sm font-medium text-cream disabled:opacity-40"
              disabled={exporting}
              onClick={() => void exportVideo()}
            >
              {exporting ? "Exporting…" : "Export video"}
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
