import { useCallback, useEffect, useRef, useState } from "react";

type LoadingImage = {
  src: string;
  caption?: string;
};

type LoadingManifest = {
  startupId?: string;
  generatedAt?: string;
  durationSecondsPerImage?: number;
  maxDurationSeconds?: number;
  images?: Array<string | LoadingImage>;
};

const MANIFEST_URL = "/loading/manifest.json";
const MIN_DURATION_MS = 2600;
const FADE_OUT_MS = 900;
const MANIFEST_POLL_MS = 5_000;
const ROTATION_STORAGE_KEY = "pigeonlab.startupArtworkRotation.v1";
const DEFAULT_IMAGES: LoadingImage[] = [
  { src: "/loading/EVA.PNG" },
  { src: "/loading/HAL.PNG" },
  { src: "/loading/WALLE.PNG" },
];

type RotationState = {
  poolKey?: string;
  queue?: string[];
  current?: string;
  last?: string;
  lastStartupToken?: string;
};

function normalizeImages(manifest: LoadingManifest): LoadingImage[] {
  return (manifest.images ?? [])
    .map((item) => (typeof item === "string" ? { src: item } : item))
    .filter((item): item is LoadingImage => Boolean(item?.src));
}

function shuffle<T>(items: T[]): T[] {
  const next = [...items];
  for (let index = next.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1));
    const current = next[index]!;
    next[index] = next[swapIndex]!;
    next[swapIndex] = current;
  }
  return next;
}

function imagePoolKey(images: LoadingImage[]): string {
  return images.map((image) => image.src).sort().join("|");
}

function readRotationState(): RotationState {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(window.localStorage.getItem(ROTATION_STORAGE_KEY) ?? "{}");
  } catch {
    return {};
  }
}

function writeRotationState(state: RotationState) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(ROTATION_STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Storage can be disabled in private browsing; the loader still works without persistence.
  }
}

function chooseStartupImage(images: LoadingImage[], startupToken: string): LoadingImage[] {
  if (images.length <= 1) return images;

  const fallbackImage = images[0];
  if (!fallbackImage) return [];

  const bySrc = new Map(images.map((image) => [image.src, image]));
  const poolKey = imagePoolKey(images);
  const state = readRotationState();

  if (
    state.poolKey === poolKey &&
    state.lastStartupToken === startupToken &&
    state.current &&
    bySrc.has(state.current)
  ) {
    return [bySrc.get(state.current) ?? fallbackImage];
  }

  let queue =
    state.poolKey === poolKey
      ? (state.queue ?? []).filter((src) => bySrc.has(src))
      : [];

  if (queue.length === 0) {
    queue = shuffle(images.map((image) => image.src));
    if (queue.length > 1 && state.last && queue[0] === state.last) {
      const first = queue[0]!;
      queue[0] = queue[1]!;
      queue[1] = first;
    }
  }

  const selectedSrc = queue.shift() ?? fallbackImage.src;
  const selected = bySrc.get(selectedSrc) ?? fallbackImage;
  writeRotationState({
    poolKey,
    queue,
    current: selected.src,
    last: selected.src,
    lastStartupToken: startupToken,
  });
  return [selected];
}

function durationFor(manifest?: LoadingManifest | null): number {
  const perImage = Math.max(3.2, manifest?.durationSecondsPerImage ?? 5.2);
  const maxDuration = Math.max(4, manifest?.maxDurationSeconds ?? 8);
  return Math.max(MIN_DURATION_MS, Math.min(maxDuration * 1000, perImage * 1000));
}

function createStartupToken(): string {
  if (typeof window !== "undefined" && window.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function LoadingRail({ progress, side }: { progress: number; side: "left" | "right" }) {
  const sideClass = side === "left" ? "left-4 sm:left-7" : "right-4 sm:right-7";

  return (
    <div
      className={`pointer-events-none absolute top-1/2 z-20 flex h-[min(68vh,34rem)] w-7 -translate-y-1/2 items-center justify-center ${sideClass}`}
      aria-hidden="true"
    >
      <div className="relative h-full w-2 overflow-hidden rounded-full border border-white/15 bg-white/10 shadow-[0_0_28px_rgba(94,234,212,0.2)]">
        <div
          className="absolute inset-x-0 bottom-0 rounded-full bg-gradient-to-t from-cyan-300 via-teal-200 to-white transition-[height] duration-150 ease-out"
          style={{ height: `${progress}%` }}
        />
        <div
          className="absolute inset-x-0 bottom-0 transition-[height] duration-150 ease-out"
          style={{ height: `${progress}%` }}
        >
          <div className="absolute -top-3 left-1/2 h-7 w-7 -translate-x-1/2 rounded-full bg-teal-100/90 blur-md" />
        </div>
      </div>
      <div className="absolute inset-y-4 left-1/2 flex -translate-x-1/2 flex-col justify-between">
        {Array.from({ length: 9 }).map((_, index) => (
          <span key={index} className="h-px w-5 bg-white/20" />
        ))}
      </div>
    </div>
  );
}

export default function StartupLoadingScreen() {
  const fallbackStartupTokenRef = useRef(createStartupToken());
  const [images, setImages] = useState<LoadingImage[]>(() => DEFAULT_IMAGES.slice(0, 1));
  const [durationMs, setDurationMs] = useState(() => durationFor());
  const [elapsedMs, setElapsedMs] = useState(0);
  const [ready, setReady] = useState(true);
  const [dismissed, setDismissed] = useState(false);
  const [fading, setFading] = useState(false);
  const [cycleKey, setCycleKey] = useState(0);
  const lastStartupIdRef = useRef<string | null>(null);

  const beginCycle = useCallback(
    (nextImages: LoadingImage[], nextDurationMs: number, startupToken: string) => {
      setImages(chooseStartupImage(nextImages, startupToken));
      setDurationMs(nextDurationMs);
      setElapsedMs(0);
      setFading(false);
      setDismissed(false);
      setReady(true);
      setCycleKey((key) => key + 1);
    },
    [],
  );

  const loadManifest = useCallback(
    async (mode: "initial" | "poll") => {
      let manifest: LoadingManifest | null = null;
      try {
        const response = await fetch(`${MANIFEST_URL}?t=${Date.now()}`, { cache: "no-store" });
        manifest = response.ok ? ((await response.json()) as LoadingManifest) : null;
      } catch {
        manifest = null;
      }

      const loadedImages = manifest ? normalizeImages(manifest) : [];
      const nextImages = loadedImages.length > 0 ? loadedImages : DEFAULT_IMAGES;
      const nextDurationMs = durationFor(manifest);
      const manifestId = manifest?.startupId ?? manifest?.generatedAt ?? null;
      const startupToken = manifestId ?? fallbackStartupTokenRef.current;

      if (mode === "initial") {
        lastStartupIdRef.current = manifestId;
        beginCycle(nextImages, nextDurationMs, startupToken);
        return;
      }

      if (manifestId && lastStartupIdRef.current && manifestId !== lastStartupIdRef.current) {
        lastStartupIdRef.current = manifestId;
        beginCycle(nextImages, nextDurationMs, startupToken);
      } else if (manifestId && !lastStartupIdRef.current) {
        lastStartupIdRef.current = manifestId;
      }
    },
    [beginCycle],
  );

  useEffect(() => {
    void loadManifest("initial");
    const interval = window.setInterval(() => void loadManifest("poll"), MANIFEST_POLL_MS);
    return () => window.clearInterval(interval);
  }, [loadManifest]);

  useEffect(() => {
    if (!ready || dismissed) return;

    let animationFrame = 0;
    const startedAt = performance.now();

    const tick = (now: number) => {
      const nextElapsed = Math.min(durationMs, now - startedAt);
      setElapsedMs(nextElapsed);

      if (nextElapsed >= durationMs) {
        setFading(true);
        window.setTimeout(() => setDismissed(true), FADE_OUT_MS);
        return;
      }

      animationFrame = requestAnimationFrame(tick);
    };

    animationFrame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animationFrame);
  }, [cycleKey, dismissed, durationMs, ready]);

  if (dismissed || images.length === 0) return null;

  const progress = Math.min(100, (elapsedMs / durationMs) * 100);
  const activeImage = images[0];
  if (!activeImage) return null;

  return (
    <div
      className={`fixed inset-0 z-[100] overflow-hidden bg-[#05080a] text-white transition-opacity duration-[900ms] ${
        fading ? "opacity-0" : "opacity-100"
      }`}
      role="status"
      aria-live="polite"
      aria-label="Loading PigeonLab"
    >
      <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(20,184,166,0.16),transparent_18%,transparent_82%,rgba(20,184,166,0.16)),linear-gradient(180deg,rgba(255,255,255,0.05),rgba(5,8,10,0.52)_32%,rgba(5,8,10,0.82))]" />

      <LoadingRail progress={progress} side="left" />
      <LoadingRail progress={progress} side="right" />

      <div className="relative z-10 flex h-full w-full items-center justify-center px-14 py-8 sm:px-24 lg:px-32">
        <img
          key={`${cycleKey}-${activeImage.src}`}
          src={activeImage.src}
          alt=""
          aria-hidden="true"
          className="max-h-[86vh] max-w-[86vw] object-contain opacity-100 drop-shadow-[0_22px_70px_rgba(0,0,0,0.48)] transition-opacity duration-700 ease-out"
          draggable={false}
        />
      </div>
    </div>
  );
}
