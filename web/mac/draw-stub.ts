export async function drawAvatar(): Promise<{ ok: false; error: string }> {
  return {
    ok: false,
    error: "This Mac app uses the cast already inside it. New drawings are in the browser studio.",
  };
}

export async function drawMouths(): Promise<{ ok: false; error: string }> {
  return {
    ok: false,
    error: "This Mac app uses the mouth parts already inside it.",
  };
}
