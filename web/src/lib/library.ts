import type { MouthName } from "@/lib/mouths";

export type SavedAvatar = {
  id: string;
  name: string;
  note: string;
  photo: string;
  avatar: string;
  mouths?: Partial<Record<MouthName, string>>;
  mouthX: number;
  mouthY: number;
  mouthScale: number;
  savedAt: number;
};

const DB_NAME = "paper-mic";
const STORE = "avatars";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE)) {
        req.result.createObjectStore(STORE, { keyPath: "id" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error ?? new Error("Could not open the cast library."));
  });
}

export async function listAvatars(): Promise<SavedAvatar[]> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const req = db.transaction(STORE, "readonly").objectStore(STORE).getAll();
    req.onsuccess = () => {
      const rows = (req.result as SavedAvatar[]).sort((a, b) => b.savedAt - a.savedAt);
      resolve(rows);
    };
    req.onerror = () => reject(req.error ?? new Error("Could not read saved avatars."));
  });
}

export async function keepAvatar(avatar: SavedAvatar): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const req = db.transaction(STORE, "readwrite").objectStore(STORE).put(avatar);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error ?? new Error("Could not save that avatar."));
  });
}

export async function forgetAvatar(id: string): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const req = db.transaction(STORE, "readwrite").objectStore(STORE).delete(id);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error ?? new Error("Could not remove that avatar."));
  });
}
