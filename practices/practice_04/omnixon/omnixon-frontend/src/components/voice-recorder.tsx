import { useCallback, useEffect, useRef, useState } from 'react'
import { MicIcon, SendIcon, SquareIcon, XIcon } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { InputGroupButton } from '@/components/ui/input-group'
import { blobToBase64, fmtClock, toWavBlob } from '@/lib/voice'
import type { Attachment } from '@/lib/types'

type Phase = 'idle' | 'recording' | 'encoding'

/** The live waveform of the microphone: bars that follow the loudness (an analyser on the stream, drawn on a canvas). */
function LiveWaveform({ stream, width = 120, height = 20 }: { stream: MediaStream; width?: number; height?: number }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const el = canvas.current
    if (!el) return
    const context = new AudioContext()
    const analyser = context.createAnalyser()
    analyser.fftSize = 256
    context.createMediaStreamSource(stream).connect(analyser)
    const data = new Uint8Array(analyser.frequencyBinCount)
    const draw = el.getContext('2d')!
    const bars = Math.floor(width / 3)
    let frame = 0
    const tick = () => {
      analyser.getByteFrequencyData(data)
      draw.clearRect(0, 0, width, height)
      draw.fillStyle = getComputedStyle(el).color
      for (let i = 0; i < bars; i++) {
        const level = data[Math.floor((i / bars) * data.length * 0.7)] / 255
        const h = Math.max(2, level * height)
        draw.fillRect(i * 3, (height - h) / 2, 2, h)
      }
      frame = requestAnimationFrame(tick)
    }
    tick()
    return () => {
      cancelAnimationFrame(frame)
      void context.close()
    }
  }, [stream, width, height])
  return <canvas ref={canvas} width={width} height={height} aria-hidden className="text-primary" />
}

/**
 * Record a voice message in the browser and hand it over as a WAV file. The recording shows its live waveform and
 * a clock; "Send" ends it and sends it at once, "Attach" ends it and keeps it in the message (to add text or more
 * files first), the cross throws it away. The WAV goes to the model as an ordinary audio attachment: a model that
 * cannot listen answers with its own error, which is shown like any other.
 */
export function VoiceRecorder({
  disabled,
  onRecorded,
}: {
  disabled?: boolean
  /** `send`: the recording was ended with "Send". */
  onRecorded: (file: Attachment, send: boolean) => void
}) {
  const [phase, setPhase] = useState<Phase>('idle')
  const [recorder, setRecorder] = useState<MediaRecorder | null>(null)
  const [seconds, setSeconds] = useState(0)
  const chunks = useRef<Blob[]>([])
  const stream = useRef<MediaStream | null>(null)
  const sendWhenDone = useRef(false)
  const discard = useRef(false)

  const release = useCallback(() => {
    stream.current?.getTracks().forEach((t) => t.stop())
    stream.current = null
  }, [])

  useEffect(() => () => release(), [release])
  useEffect(() => {
    if (phase !== 'recording') return
    const started = Date.now()
    const timer = setInterval(() => setSeconds((Date.now() - started) / 1000), 200)
    return () => clearInterval(timer)
  }, [phase])

  async function start() {
    if (!navigator.mediaDevices?.getUserMedia) return void toast.error('This browser cannot record sound (it needs a secure page).')
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch (e) {
      return void toast.error(`The microphone is not available: ${(e as Error).message || 'permission denied'}`)
    }
    chunks.current = []
    discard.current = false
    const media = new MediaRecorder(stream.current)
    media.ondataavailable = (e) => e.data.size && chunks.current.push(e.data)
    media.onstop = async () => {
      release()
      setRecorder(null)
      if (discard.current) return setPhase('idle')
      setPhase('encoding')
      try {
        const wav = await toWavBlob(new Blob(chunks.current, { type: media.mimeType }))
        const name = `voice-${new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)}.wav`
        onRecorded({ data: await blobToBase64(wav), media_type: 'audio/wav', name }, sendWhenDone.current)
      } catch (e) {
        toast.error(`Could not make a WAV file of the recording: ${(e as Error).message}`)
      } finally {
        setPhase('idle')
      }
    }
    media.start(250)
    setSeconds(0)
    setRecorder(media)
    setPhase('recording')
  }

  function finish(send: boolean) {
    sendWhenDone.current = send
    recorder?.stop()
  }
  function cancel() {
    discard.current = true
    recorder?.stop()
  }

  if (phase === 'idle')
    return (
      <InputGroupButton variant="secondary" aria-label="Record voice" disabled={disabled} onClick={start}>
        <MicIcon /> Voice
      </InputGroupButton>
    )

  return (
    <div role="group" aria-label="Recording" className="flex h-7 items-center gap-2 rounded-md border bg-background pr-1 pl-2">
      {phase === 'encoding' ? (
        <span className="flex items-center gap-2 text-xs text-muted-foreground">
          <Spinner /> Making a WAV…
        </span>
      ) : (
        <>
          <span aria-hidden className="size-2 animate-pulse rounded-full bg-destructive" />
          <span className="value-mono w-10 text-xs tabular-nums" aria-label="Recording time">
            {fmtClock(seconds)}
          </span>
          {recorder && stream.current && <LiveWaveform stream={stream.current} />}
          <Button type="button" variant="ghost" size="icon-xs" aria-label="Discard the recording" onClick={cancel}>
            <XIcon />
          </Button>
          <Button type="button" variant="secondary" size="xs" onClick={() => finish(false)}>
            <SquareIcon /> Attach
          </Button>
          <Button type="button" size="xs" onClick={() => finish(true)}>
            <SendIcon /> Send
          </Button>
        </>
      )}
    </div>
  )
}
