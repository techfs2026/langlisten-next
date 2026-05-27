//! Streaming linear-interpolation resampler + channel remapper.
//!
//! Fed interleaved f32 source samples; emits interleaved f32 at the device's
//! sample rate and channel count. State is carried across calls so packet
//! boundaries don't introduce clicks.

pub struct Resampler {
    source_sr: u32,
    source_ch: usize,
    output_sr: u32,
    output_ch: usize,
    rate_ratio: f64, // source_sr / output_sr — how many source frames advance per output frame
    last_frame: Vec<f32>,
    has_last: bool,
    /// Position in source frames at which the next output frame should be sampled.
    /// 0.0 means "at last_frame"; 1.0 means "at src[0]" of next input buffer; etc.
    src_pos: f64,
}

impl Resampler {
    pub fn new(source_sr: u32, source_ch: usize, output_sr: u32, output_ch: usize) -> Self {
        Self {
            source_sr,
            source_ch,
            output_sr,
            output_ch,
            rate_ratio: source_sr as f64 / output_sr.max(1) as f64,
            last_frame: vec![0.0; source_ch.max(1)],
            has_last: false,
            src_pos: 0.0,
        }
    }

    pub fn passthrough(&self) -> bool {
        self.source_sr == self.output_sr && self.source_ch == self.output_ch
    }

    pub fn reset(&mut self) {
        self.has_last = false;
        self.src_pos = 0.0;
        for v in self.last_frame.iter_mut() {
            *v = 0.0;
        }
    }

    /// Convert interleaved source samples and append device-format interleaved samples to `out`.
    pub fn process(&mut self, src: &[f32], out: &mut Vec<f32>) {
        if self.source_ch == 0 || self.output_ch == 0 {
            return;
        }
        if self.passthrough() {
            out.extend_from_slice(src);
            return;
        }

        let src_ch = self.source_ch;
        let src_frames = src.len() / src_ch;
        if src_frames == 0 {
            return;
        }

        let mut temp = vec![0.0f32; src_ch];

        // We sample at positions [0, src_frames). Position p means:
        //   floor=0  → interpolate (last_frame, src[0])
        //   floor=k>0 → interpolate (src[k-1], src[k])
        // If we have no history yet, we anchor src_pos to 0.0 (start at src[0]).
        if !self.has_last && self.src_pos < 1.0 {
            self.src_pos = 0.0;
        }

        let mut p = self.src_pos;
        let frames_f = src_frames as f64;

        while p < frames_f {
            let idx_floor = p.floor() as usize;
            let frac = (p - idx_floor as f64) as f32;
            let one_minus = 1.0 - frac;

            if idx_floor == 0 {
                let right = &src[0..src_ch];
                if self.has_last {
                    for c in 0..src_ch {
                        temp[c] = self.last_frame[c] * one_minus + right[c] * frac;
                    }
                } else {
                    // No history: emit src[0] directly.
                    temp.copy_from_slice(right);
                }
            } else {
                let l = (idx_floor - 1) * src_ch;
                let r = idx_floor * src_ch;
                let left = &src[l..l + src_ch];
                let right = &src[r..r + src_ch];
                for c in 0..src_ch {
                    temp[c] = left[c] * one_minus + right[c] * frac;
                }
            }

            self.write_output_frame(&temp, out);
            p += self.rate_ratio;
        }

        // Save last source frame for next call and carry over fractional position.
        let last_start = (src_frames - 1) * src_ch;
        self.last_frame
            .copy_from_slice(&src[last_start..last_start + src_ch]);
        self.has_last = true;
        self.src_pos = p - frames_f;
    }

    fn write_output_frame(&self, src_frame: &[f32], out: &mut Vec<f32>) {
        let sc = src_frame.len();
        let oc = self.output_ch;
        if sc == oc {
            out.extend_from_slice(src_frame);
            return;
        }
        if sc == 1 {
            // Mono → N: duplicate to first two channels (or all), zero rest beyond stereo.
            let v = src_frame[0];
            for c in 0..oc {
                out.push(if c < 2 { v } else { 0.0 });
            }
            return;
        }
        if oc == 1 {
            // N → mono: simple average.
            let mut sum = 0.0f32;
            for v in src_frame {
                sum += *v;
            }
            out.push(sum / sc as f32);
            return;
        }
        // Generic mismatch (e.g. stereo→5.1): copy as many channels as we can, pad the rest with 0.
        let n = sc.min(oc);
        for c in 0..n {
            out.push(src_frame[c]);
        }
        for _ in n..oc {
            out.push(0.0);
        }
    }
}
