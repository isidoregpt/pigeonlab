import { useCallback, useEffect, useMemo, useRef, useState } from "react";

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
const DEFAULT_IMAGES: LoadingImage[] = [
  { src: "/loading/HAL.PNG", caption: "HAL" },
  { src: "/loading/WALLE.PNG", caption: "WALLE" },
];

function normalizeImages(manifest: LoadingManifest): LoadingImage[] {
  return (manifest.images ?? [])
    .map((item) => (typeof item === "string" ? { src: item } : item))
    .filter((item) => Boolean(item.src));
}

function rotateImages(images: LoadingImage[]): LoadingImage[] {
  if (images.length <= 1) return images;
  const offset = Math.floor(Math.random() * images.length);
  return [...images.slice(offset), ...images.slice(0, offset)];
}

function durationFor(images: LoadingImage[], manifest?: LoadingManifest | null): number {
  const perImage = Math.max(2.8, manifest?.durationSecondsPerImage ?? 4.5);
  const maxDuration = Math.max(6, manifest?.maxDurationSeconds ?? 24);
  return Math.max(
    MIN_DURATION_MS,
    Math.min(maxDuration * 1000, images.length * perImage * 1000),
  );
}

export default function StartupLoadingScreen() {
  const [images, setImages] = useState<LoadingImage[]>(() => rotateImages(DEFAULT_IMAGES));
  const [durationMs, setDurationMs] = useState(() => durationFor(DEFAULT_IMAGES));
  const [elapsedMs, setElapsedMs] = useState(0);
  const [ready, setReady] = useState(true);
  const [dismissed, setDismissed] = useState(false);
  const [fading, setFading] = useState(false);
  const [cycleKey, setCycleKey] = useState(0);
  const lastStartupIdRef = useRef<string | null>(null);

  const beginCycle = useCallback((nextImages: LoadingImage[], nextDurationMs: number) => {
    setImages(rotateImages(nextImages));
    setDurationMs(nextDurationMs);
    setElapsedMs(0);
    setFading(false);
    setDismissed(false);
    setReady(true);
    setCycleKey((key) => key + 1);
  }, []);

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
      const nextDurationMs = durationFor(nextImages, manifest);
      const manifestId = manifest?.startupId ?? manifest?.generatedAt ?? null;

      if (mode === "initial") {
        lastStartupIdRef.current = manifestId;
        beginCycle(nextImages, nextDurationMs);
        return;
      }

      if (manifestId && lastStartupIdRef.current && manifestId !== lastStartupIdRef.current) {
        lastStartupIdRef.current = manifestId;
        beginCycle(nextImages, nextDurationMs);
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

  const activeIndex = useMemo(() => {
    if (images.length <= 1) return 0;
    const progress = Math.min(0.999, elapsedMs / Math.max(durationMs, 1));
    return Math.min(images.length - 1, Math.floor(progress * images.length));
  }, [durationMs, elapsedMs, images.length]);

  if (dismissed || images.length === 0) return null;

  const progress = Math.min(100, Math.round((elapsedMs / durationMs) * 100));
  const activeImage = images[activeIndex] ?? images[0];
  if (!activeImage) return null;

  return (
    <div
      className={`fixed inset-0 z-[100] overflow-hidden bg-[#071014] text-white transition-opacity duration-[900ms] ${
        fading ? "opacity-0" : "opacity-100"
      }`}
      role="status"
      aria-live="polite"
    >
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_15%,rgba(13,148,136,0.28),transparent_34%),linear-gradient(180deg,rgba(7,16,20,0.08),rgba(7,16,20,0.86))]" />

      <div className="relative flex h-full w-full items-center justify-center px-5 py-8">
        {images.map((image, index) => (
          <img
            key={image.src}
            src={image.src}
            alt={image.caption || "PigeonLab loading artwork"}
            className={`absolute max-h-full max-w-full object-contain transition-opacity duration-1000 ease-out ${
              index === activeIndex ? "opacity-100" : "opacity-0"
            }`}
            draggable={false}
          />
        ))}

        <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-[#071014] via-[#071014]/78 to-transparent px-6 pb-7 pt-28">
          <div className="mx-auto flex w-full max-w-3xl items-end gap-5">
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold uppercase tracking-[0.28em] text-teal-100/85">
                PigeonLab
              </div>
              <div className="mt-1 truncate text-lg font-semibold text-white sm:text-2xl">
                {activeImage.caption || "Preparing the lab"}
              </div>
              <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/16">
                <div
                  className="h-full rounded-full bg-teal-300 transition-[width] duration-150"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
            <button
              type="button"
              onClick={() => {
                setFading(true);
                window.setTimeout(() => setDismissed(true), 180);
              }}
              className="pointer-events-auto shrink-0 rounded-md border border-white/20 bg-white/10 px-3 py-2 text-sm font-medium text-white/85 transition hover:bg-white/18 focus:outline-none focus:ring-2 focus:ring-teal-200"
            >
              Skip
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
