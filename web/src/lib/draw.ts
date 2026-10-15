import { createServerFn } from "@tanstack/react-start";

const AVATAR_PROMPT =
  "Redraw this headshot as a hand-drawn ink and watercolor podcast avatar. Bust from mid-chest up, facing the camera, mouth gently closed. Keep this exact person's recognizable face, hair, glasses, facial hair, and clothing colors. Visible pencil line, soft watercolor wash, plain warm cream paper background, generous margin, no text, no watermark, no border.";

const MOUTH_PROMPT =
  "Using this person's drawn face as the style reference, output ONLY a precise 3-column by 2-row grid of six mouths, no full faces. Solid flat background exactly #FF00FF. Top row left to right: closed lip line, small open mouth, medium talking mouth. Bottom row: wide open mouth, round O mouth, teeth-on-lip. Same ink line as the reference, each mouth centered in its cell, nothing crossing cell edges, no labels, no text.";

type DrawResult = { ok: true; image: string } | { ok: false; error: string };

async function imagine(prompt: string, imageDataUrl: string): Promise<DrawResult> {
  const apiKey = process.env.XAI_API_KEY;
  if (!apiKey) return { ok: false, error: "Drawing is unavailable right now." };

  const res = await fetch("https://api.x.ai/v1/images/edits", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: "grok-imagine-image",
      prompt,
      image: { url: imageDataUrl, type: "image_url" },
      response_format: "b64_json",
    }),
  });

  if (!res.ok) {
    return { ok: false, error: `Drawing failed (${res.status}). Try a clearer headshot.` };
  }

  const body = (await res.json()) as {
    data?: { b64_json?: string; url?: string }[];
  };
  const item = body.data?.[0];
  if (item?.b64_json) return { ok: true, image: `data:image/jpeg;base64,${item.b64_json}` };
  if (item?.url) return { ok: true, image: item.url };
  return { ok: false, error: "No drawing came back. Try again." };
}

function checkPhoto(imageDataUrl: string) {
  if (!imageDataUrl.startsWith("data:image/")) {
    throw new Error("That file is not a photo.");
  }
  if (imageDataUrl.length > 1_800_000) {
    throw new Error("That photo is too large. Use a closer crop.");
  }
}

export const drawAvatar = createServerFn({ method: "POST" })
  .validator((input: { imageDataUrl: string; note?: string }) => {
    checkPhoto(input.imageDataUrl);
    return {
      imageDataUrl: input.imageDataUrl,
      note: (input.note ?? "").slice(0, 200),
    };
  })
  .handler(async ({ data }) => {
    const extra = data.note ? ` Extra direction: ${data.note}` : "";
    return imagine(AVATAR_PROMPT + extra, data.imageDataUrl);
  });

export const drawMouths = createServerFn({ method: "POST" })
  .validator((input: { imageDataUrl: string }) => {
    checkPhoto(input.imageDataUrl);
    return input;
  })
  .handler(async ({ data }) => imagine(MOUTH_PROMPT, data.imageDataUrl));
