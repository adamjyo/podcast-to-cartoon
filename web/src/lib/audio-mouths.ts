import type { MouthName } from "@/lib/mouths";

export const HOP_MS = 50;

const OPEN: Record<MouthName, number> = {
  closed: 0,
  small: 1,
  medium: 2,
  teeth: 3,
  round: 4,
  wide: 5,
};

export function mouthForLevel(rms: number, zcr: number): MouthName {
  if (rms < 0.018) return "closed";
  if (zcr > 0.16 && rms > 0.03) return "teeth";
  if (rms < 0.045) return "small";
  if (rms < 0.09) return "medium";
  if (rms < 0.15) return "wide";
  return zcr < 0.09 ? "round" : "wide";
}

/** Hold a closed mouth for one extra frame so quiet gaps don't chatter. */
export function settle(track: MouthName[]): MouthName[] {
  return track.map((shape, i) => {
    if (shape !== "closed") return shape;
    const prev = track[i - 1];
    if (prev && prev !== "closed") return "small";
    return "closed";
  });
}

export function shapeOnTrack(track: MouthName[], ms: number): MouthName {
  if (!track.length) return "closed";
  const index = Math.min(track.length - 1, Math.max(0, Math.floor(ms / HOP_MS)));
  return track[index] ?? "closed";
}

export function openness(shape: MouthName): number {
  return OPEN[shape];
}

export async function readSpeech(file: File): Promise<{
  durationMs: number;
  track: MouthName[];
  url: string;
}> {
  const audio = new AudioContext();
  try {
    const buffer = await audio.decodeAudioData(await file.arrayBuffer());
    const data = buffer.getChannelData(0);
    const hop = Math.max(1, Math.round(buffer.sampleRate * (HOP_MS / 1000)));
    const raw: MouthName[] = [];
    for (let i = 0; i < data.length; i += hop) {
      const end = Math.min(data.length, i + hop);
      let sum = 0;
      let crossings = 0;
      let prev = data[i] ?? 0;
      for (let j = i; j < end; j += 1) {
        const sample = data[j] ?? 0;
        sum += sample * sample;
        if ((sample >= 0 && prev < 0) || (sample < 0 && prev >= 0)) crossings += 1;
        prev = sample;
      }
      const count = Math.max(1, end - i);
      raw.push(mouthForLevel(Math.sqrt(sum / count), crossings / count));
    }
    return {
      durationMs: Math.round(buffer.duration * 1000),
      track: settle(raw),
      url: URL.createObjectURL(file),
    };
  } finally {
    await audio.close();
  }
}
