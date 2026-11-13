declare module 'audiobuffer-to-wav' {
  /** Encodes an AudioBuffer as WAVE (16-bit PCM by default). */
  export default function toWav(buffer: AudioBuffer, options?: { float32?: boolean }): ArrayBuffer
}
