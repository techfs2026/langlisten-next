export function fmtTime(s: number): string {
    if (!isFinite(s) || s < 0) return "0:00";
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${String(sec).padStart(2, "0")}`;
  }
  
  export function trim(s: string, n: number): string {
    return s.length > n ? s.slice(0, n) + "…" : s;
  }
  
  /** Parse "Artist - Title.ext" filename into {title, artist}. Artist is null when the filename doesn't carry one. */
  export function parseName(fileName: string): { title: string; artist: string | null } {
    const full = fileName.replace(/\.[^.]+$/, "");
    if (full.includes(" - ")) {
      const parts = full.split(" - ");
      const artist = parts[0].trim();
      const title = parts.slice(1).join(" - ").trim();
      return { title: title || full, artist: artist || null };
    }
    return { title: full, artist: null };
  }

  export function fmtSampleRateKHz(sr: number): string {
    if (!sr) return "";
    const k = sr / 1000;
    // 44.1, 88.2, 176.4 need a decimal; whole-number rates don't.
    return Number.isInteger(k) ? `${k} kHz` : `${k.toFixed(1)} kHz`;
  }

  export function fmtChannels(ch: number): string {
    if (ch <= 0) return "";
    if (ch === 1) return "MONO";
    if (ch === 2) return "STEREO";
    if (ch === 6) return "5.1";
    if (ch === 8) return "7.1";
    return `${ch} CH`;
  }