import React, { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { TutorProfile } from '../lib/tutorProfiles'
import type { VoiceSessionApi } from '../hooks/useVoiceSession'
import type { LangStrings } from '../lib/tutorI18n'
import { MOCKUP_VOICE_SUB } from '../lib/voiceStates'
import { IconKeyboard, IconMic, IconStop, IconXClose, IconClock } from './Icons'
import { MentorOrb } from './MentorOrb'
import type { MentorOrbState } from './MentorOrb'
import { getToken } from '../lib/api'
import { isBraveBrowser } from '../lib/browserDetect'

const ARABIC_RE = /[\u0600-\u06FF]/

// Inline record-dot icon replacing the U+23FA "record" glyph, which has no
// reliable glyph in the Windows font stack and renders as a mangled fallback.
function MicRecordDot() {
  return (
    <svg width="11" height="11" viewBox="0 0 12 12" aria-hidden="true" className="v-rec-dot">
      <circle cx="6" cy="6" r="4.5" fill="currentColor" />
    </svg>
  )
}

type AudioContextWindow = Window & typeof globalThis & {
  webkitAudioContext?: typeof AudioContext
}

/**
 * Browser autoplay policies can block the async `audio.play()` that happens
 * AFTER the /tutor + /tutor/tts round trip (no longer inside a user gesture).
 * VoiceMode mounts within the Live-button gesture, so unlock media playback
 * there once: a silent buffer source gets the page's media session started and
 * the subsequent speech blob plays without a console "play() failed" abort.
 */
function primeAutoplay(): void {
  try {
    const win = typeof window === 'undefined' ? null : (window as AudioContextWindow)
    if (!win) return
    const Ctor = win.AudioContext ?? win.webkitAudioContext
    if (!Ctor) return
    const ctx = new Ctor()
    const src = ctx.createBufferSource()
    src.buffer = ctx.createBuffer(1, 1, 22050)
    src.connect(ctx.destination)
    void src.start(0)
    void ctx.resume().then(() => window.setTimeout(() => void ctx.close().catch(() => { /* closed */ }), 0))
  } catch { /* audio unsupported — playback will surface its own error */ }
}

function messageDir(text: string): 'rtl' | 'ltr' {
  const ar = (text.match(ARABIC_RE) || []).length
  const en = (text.match(/[A-Za-z]/g) || []).length
  return ar > 0 && ar >= en ? 'rtl' : 'ltr'
}

/* ── WAV encoding utility ───────────────────────────────────────────────── */

function encodeWav(samples: Float32Array, sampleRate: number): string {
  const numChannels = 1
  const bitsPerSample = 16
  const bytesPerSample = bitsPerSample / 8
  const blockAlign = numChannels * bytesPerSample
  const dataLength = samples.length * bytesPerSample
  const buffer = new ArrayBuffer(44 + dataLength)
  const view = new DataView(buffer)

  const writeStr = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i))
  }

  writeStr(0, 'RIFF')
  view.setUint32(4, 36 + dataLength, true)
  writeStr(8, 'WAVE')
  writeStr(12, 'fmt ')
  view.setUint32(16, 16, true)          // chunk size
  view.setUint16(20, 1, true)           // PCM format
  view.setUint16(22, numChannels, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * blockAlign, true)
  view.setUint16(32, blockAlign, true)
  view.setUint16(34, bitsPerSample, true)
  writeStr(36, 'data')
  view.setUint32(40, dataLength, true)

  // Float32 → Int16 PCM
  let offset = 44
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(offset, s * 0x7FFF, true)
  }

  // Base64 encode
  const bytes = new Uint8Array(buffer)
  let binary = ''
  const chunkSize = 8192
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize)
    binary += String.fromCharCode(...chunk)
  }
  return btoa(binary)
}

/* ── Server-side STT push-to-talk hook ──────────────────────────────────── */

function useServerSTT(studentId: number, language: 'en' | 'ar') {
  const ctxRef = useRef<AudioContext | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Float32Array[]>([])
  const sampleRateRef = useRef(16000)
  const isRecordingRef = useRef(false)
  const sendingRef = useRef(false)
  const [isRecording, setIsRecording] = useState(false)
  const [isSending, setIsSending] = useState(false)

  const cleanup = useCallback(() => {
    try { processorRef.current?.disconnect() } catch { /* already disconnected */ }
    try { sourceRef.current?.disconnect() } catch { /* already disconnected */ }
    try { streamRef.current?.getTracks().forEach(t => t.stop()) } catch { /* closed */ }
    try { void ctxRef.current?.close() } catch { /* closed */ }
    ctxRef.current = null
    processorRef.current = null
    sourceRef.current = null
    streamRef.current = null
    chunksRef.current = []
  }, [])

  const startRecording = useCallback(async () => {
    if (isRecordingRef.current) return
    isRecordingRef.current = true
    cleanup()
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, sampleRate: 16000 }
      })
      const AudioCtx = window.AudioContext || (window as AudioContextWindow).webkitAudioContext
      const ctx = new AudioCtx()
      sampleRateRef.current = ctx.sampleRate
      const source = ctx.createMediaStreamSource(stream)
      const processor = ctx.createScriptProcessor(4096, 1, 1)

      chunksRef.current = []
      processor.onaudioprocess = (e) => {
        const input = e.inputBuffer.getChannelData(0)
        chunksRef.current.push(new Float32Array(input))
      }

      source.connect(processor)
      // Feed the mic through a zero-gain node (never straight to the speakers):
      // a direct destination connection would loop the mentor's TTS audio back
      // into the recording as a self-echo while still letting ScriptProcessor
      // onaudioprocess fire for the captured PCM.
      const mute = ctx.createGain()
      mute.gain.value = 0
      processor.connect(mute)
      mute.connect(ctx.destination)

      streamRef.current = stream
      ctxRef.current = ctx
      sourceRef.current = source
      processorRef.current = processor
      isRecordingRef.current = true
      setIsRecording(true)
    } catch {
      cleanup()
      isRecordingRef.current = false
    }
  }, [cleanup])

  const stopRecording = useCallback(async (): Promise<string | null> => {
    if (!isRecordingRef.current) {
      cleanup()
      setIsRecording(false)
      return null
    }
    if (sendingRef.current) return null
    isRecordingRef.current = false
    sendingRef.current = true

    // Merge chunks into single Float32Array
    let totalLen = 0
    for (const c of chunksRef.current) totalLen += c.length
    const merged = new Float32Array(totalLen)
    let off = 0
    for (const c of chunksRef.current) {
      merged.set(c, off)
      off += c.length
    }

    cleanup()
    setIsRecording(false)

    // Resample to 16kHz if needed
    const targetRate = 16000
    const srcRate = sampleRateRef.current
    let pcm = merged
    if (srcRate !== targetRate) {
      const ratio = targetRate / srcRate
      const newLen = Math.round(merged.length * ratio)
      pcm = new Float32Array(newLen)
      for (let i = 0; i < newLen; i++) {
        const srcIdx = i / ratio
        const lo = Math.floor(srcIdx)
        const hi = Math.min(lo + 1, merged.length - 1)
        const frac = srcIdx - lo
        pcm[i] = merged[lo] * (1 - frac) + merged[hi] * frac
      }
    }

    // Skip if recording was too short (<0.5s) — holds the mic at least half a
    // second, otherwise the accidental-tap counts as a no-op.
    if (pcm.length / targetRate < 0.5) {
      sendingRef.current = false
      return null
    }

    const wavB64 = encodeWav(pcm, targetRate)

    setIsSending(true)
    try {
      const token = getToken()
      if (!token || !studentId) return null
      const resp = await fetch(`/api/students/${studentId}/tutor/stt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ audio: wavB64, language })
      })
      if (!resp.ok) return null
      const data = await resp.json()
      return (data.text as string) || null
    } catch {
      return null
    } finally {
      setIsSending(false)
      sendingRef.current = false
    }
  }, [studentId, language, cleanup])

  return { isRecording, isSending, startRecording, stopRecording }
}

/* ── VoiceMode ──────────────────────────────────────────────────────────── */

export function VoiceMode({ voice, tutor, lang, ui, studentId, onClose }: {
  voice: VoiceSessionApi
  tutor: TutorProfile
  lang: 'en' | 'ar'
  ui: LangStrings
  studentId: number
  onClose: () => void
}) {
  // Determine if we need the server STT fallback. Brave ships a Web Speech API
  // that cannot reach Google's speech servers, so it is detected up front and
  // uses the push-to-talk recorder without ever starting the broken recognizer.
  // Any other runtime that errors out of browser STT (network / deadlock /
  // empty-error loop) also lands here via voiceUnavailable.
  const [isBrave] = useState(() => isBraveBrowser())
  const needsFallback = isBrave || voice.errorKind === 'voice-unavailable'
  const serverStt = useServerSTT(studentId, voice.language)

  // Transient spoken feedback when a recording produced no usable transcript
  // (too short / silent / STT failure) — the user must never get zero response.
  const [hint, setHint] = useState<string | null>(null)
  const hintTimer = useRef<number | undefined>(undefined)
  const showHint = useCallback((msg: string) => {
    setHint(msg)
    window.clearTimeout(hintTimer.current)
    hintTimer.current = window.setTimeout(() => setHint(null), 2600)
  }, [])

  const errorText =
    voice.errorKind === 'mic' ? ui.micDeclined
      : voice.errorKind === 'connection' ? ui.connectionLost
        : voice.error

  // Engine state remains the single source of truth. While an error is set the
  // orb shows the calm ERROR/… visual and the state line carries the error text
  // instead of "Ready"; otherwise the orb mirrors the engine state 1:1.
  const orbState: MentorOrbState = voice.error ? 'error' : voice.state

  const statusText =
    voice.error && voice.errorKind !== 'voice-unavailable' ? errorText
      : voice.state === 'listening' ? ui.listening
        : voice.state === 'processing' ? ui.thinking
          : voice.state === 'speaking' ? ui.voiceSpeaking.replace('{name}', tutor.name)
            : voice.state === 'interrupted' ? ui.voiceBargeIn
              : needsFallback
                ? (lang === 'ar' ? 'التفريغ الصوتي من الخادم مفعّل' : 'Server transcription is on')
                : ui.voiceReady

  const submitRecording = useCallback(async () => {
    const text = await serverStt.stopRecording()
    if (text) {
      setHint(null)
      voice.injectTranscript(text)
    } else {
      showHint(lang === 'ar' ? 'لم ألتقط الصوت — اضغط باستمرار وحاول مرة أخرى'
        : "Didn't catch that — hold and try again")
    }
  }, [serverStt, voice, lang, showHint])

  // Fresh callback for the window-level release handlers (avoids re-binding on
  // every render while remaining point-in-time accurate).
  const submitRef = useRef(submitRecording)
  submitRef.current = submitRecording

  // Hold-to-release: recording stops the moment the pointer is released ANYWHERE
  // on the page (not just over the mic), matching the documented gesture. A
  // pointercancel (drag off / interrupt) follows the same release path — the
  // post-submit hook reports "didn't catch that" instead of injecting silence.
  useEffect(() => {
    if (!serverStt.isRecording || serverStt.isSending) return
    const release = () => { void submitRef.current() }
    const cancel = () => { void submitRef.current() }
    window.addEventListener('pointerup', release)
    window.addEventListener('touchend', release)
    window.addEventListener('pointercancel', cancel)
    return () => {
      window.removeEventListener('pointerup', release)
      window.removeEventListener('touchend', release)
      window.removeEventListener('pointercancel', cancel)
    }
  }, [serverStt.isRecording, serverStt.isSending])

  // Hard watchdog: no matter what (missed event, cancelled gesture), a live
  // recording auto-submits after 15s so the mentor can never be silent because
  // the recorder was left hanging.
  useEffect(() => {
    if (!serverStt.isRecording) return
    const id = window.setTimeout(() => { void submitRef.current() }, 15_000)
    return () => window.clearTimeout(id)
  }, [serverStt.isRecording])

  const pointerHeldRef = useRef(false)
  const onMicPointerDown = () => {
    if (serverStt.isSending) return
    pointerHeldRef.current = true
    setHint(null)
    if (serverStt.isRecording) return
    if (needsFallback) {
      void serverStt.startRecording().then(() => {
        // The pointer was released while getUserMedia/AudioContext setup was
        // still running, so no release event will follow the arming: submit the
        // moment recording becomes live instead of leaving the recorder stuck
        // indefinitely waiting for a release that already happened.
        if (!pointerHeldRef.current) void submitRef.current()
      })
    }
  }
  const onMicPointerUp = () => {
    if (!pointerHeldRef.current) return
    pointerHeldRef.current = false
    if (serverStt.isRecording) void submitRef.current()
  }
  const onMicClick = () => {
    // A pointer gesture already handled the down/up pair; the click that follows
    // the pointerup must not double-toggle. Keyboard activation has no pointer
    // down first, so it still runs onCenter() as a tap-toggle.
    if (pointerHeldRef.current) {
      pointerHeldRef.current = false
      return
    }
    onCenter()
  }

  const onCenter = () => {
    if (serverStt.isSending) return
    if (serverStt.isRecording) {
      void submitRecording()
      return
    }
    if (needsFallback) {
      setHint(null)
      void serverStt.startRecording()
      return
    }
    if (voice.state === 'idle') voice.start()
    else if (voice.state === 'listening') voice.stop()
    else if (voice.state === 'processing' || voice.state === 'speaking') voice.interrupt()
  }

  const micLabel =
    serverStt.isRecording
      ? (lang === 'ar' ? 'ارفع الإصبع لإرسال التسجيل' : 'Release to send')
      : voice.state === 'listening' || voice.state === 'processing' || voice.state === 'speaking'
        ? ui.voiceStop
        : ui.tapTheMic

  const stopActive =
    serverStt.isRecording ||
    voice.state === 'listening' || voice.state === 'processing' || voice.state === 'speaking'

  // Fresh session each open; cleanup tears the engine + playback down.
  useEffect(() => {
    primeAutoplay()
    voice.open()
    return () => {
      voice.close()
      serverStt.stopRecording()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Dedicated fullscreen surface: the normal chat UI and the dashboard behind
  // it must not remain visible, so lock body scroll while the live session is up.
  useEffect(() => {
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = prev }
  }, [])

  const lastUser = voice.transcript.filter((t) => t.role === 'user').pop()?.text ?? ''
  const lastAgent = voice.transcript.filter((t) => t.role === 'assistant').pop()?.text ?? ''
  const err = !voice.supported && !needsFallback
    ? ui.voiceUnsupported
    : voice.error && voice.errorKind !== 'voice-unavailable' && errorText
      ? errorText
      : ''

  const reduceMotion =
    typeof window !== 'undefined' &&
    !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

  const surface = (
    <div
      className={`voice theme-${tutor.theme}`}
      data-state={voice.state}
      data-error={voice.error ? 'true' : undefined}
      role="dialog"
      aria-modal="true"
      aria-label={ui.voiceModeTitle}
      dir={voice.language === 'ar' ? 'rtl' : 'ltr'}
    >
      <header className="v-top">
        <button type="button" className="v-close" onClick={onClose} aria-label={ui.voiceClose}>
          <IconXClose size={17} />
        </button>

        <div className="v-live">
          <span className="v-live-avatar"><img src={tutor.avatar} alt="" /></span>
          <span className="v-live-name">{tutor.name}</span>
          <span className="v-live-dot" aria-hidden="true">·</span>
          <span className="v-live-tag">{ui.voiceLiveTag}</span>
        </div>

        <div className="v-lang" role="group" aria-label={ui.voiceLanguage}>
          <button
            type="button"
            className={`v-lang-btn${voice.language === 'en' ? ' is-active' : ''}`}
            onClick={() => voice.setLanguage('en')}
            aria-pressed={voice.language === 'en'}
          >
            EN
          </button>
          <span className="v-lang-sep" aria-hidden="true">|</span>
          <button
            type="button"
            className={`v-lang-btn${voice.language === 'ar' ? ' is-active' : ''}`}
            onClick={() => voice.setLanguage('ar')}
            aria-pressed={voice.language === 'ar'}
          >
            عربي
          </button>
        </div>
      </header>

      <div className="v-center">
        <div className="ml-orb-wrap">
          <MentorOrb
            mentorId={tutor.id}
            state={orbState}
            reducedMotion={reduceMotion}
            onTap={onCenter}
            ariaLabel={micLabel}
          />
        </div>

        <div className="v-state" aria-live="polite">
          <span className={`sv sv-${voice.state}`}>
            {serverStt.isRecording
              ? (lang === 'ar'
                  ? <><MicRecordDot /> سجّل — ارفع الإصبع للإرسال</>
                  : <><MicRecordDot /> Recording… release to send</>)
              : serverStt.isSending
                ? (lang === 'ar'
                    ? <><IconClock size={13} /> جارٍ التعرف...</>
                    : <><IconClock size={13} /> Transcribing…</>)
                : statusText}
          </span>
        </div>

        {hint && <div className="v-note" role="status">{hint}</div>}

        <div className="v-sub">
          <span className={`sb sb-${voice.state}`}>
            {serverStt.isRecording
              ? (lang === 'ar' ? 'ارفع الإصبع لإرسال التسجيل' : 'Release to send')
              : needsFallback
                ? (lang === 'ar' ? 'اضغط باستمرار على المايك للتسجيل، ثم ارفع الإصبع' : 'Hold the mic to record, then release')
                : MOCKUP_VOICE_SUB[voice.state][lang]}
          </span>
        </div>

        <div className="eq" aria-hidden="true"><span></span><span></span><span></span><span></span><span></span></div>

        <div className={`vc vc-${voice.state}`} aria-live="polite">
          {voice.state === 'speaking' ? (
            <div className="vc-row vc-agent">
              <span className="vc-text" dir={messageDir(lastAgent)}>{lastAgent}</span>
              <span className="vc-fade" aria-hidden="true" />
            </div>
          ) : voice.state === 'processing' ? (
            <div className="vc-row vc-user">
              <span className="vc-text" dir={messageDir(lastUser)}>{lastUser}</span>
              <span className="dots"><i></i><i></i><i></i></span>
            </div>
          ) : voice.state === 'interrupted' ? (
            <div className="vc-row vc-user">
              <span className="vc-text" dir={messageDir(lastUser)}>{lastUser}<span className="caret" /></span>
            </div>
          ) : voice.state === 'listening' ? (
            <div className="vc-row vc-user">
              <span className="vc-text" dir={messageDir(lastUser)}>{lastUser ? lastUser : '—'}<span className="caret" /></span>
            </div>
          ) : (
            <div className="vc-row vc-idle">
              <span className="vc-text">—</span>
            </div>
          )}
        </div>

        {err && <div className="v-err">{err}</div>}
      </div>

      <footer className="v-bottom">
        <div className="v-dock">
          <button type="button" className="v-keyboard" onClick={onClose} aria-label={ui.voiceKeyboard}>
            <IconKeyboard size={20} />
            <span className="v-kbd-label">{ui.voiceTypeInstead}</span>
          </button>

          <button
            type="button"
            className="v-mic"
            data-recording={serverStt.isRecording ? 'true' : undefined}
            onPointerDown={onMicPointerDown}
            onPointerUp={onMicPointerUp}
            onPointerCancel={onMicPointerUp}
            onClick={onMicClick}
            disabled={(!voice.supported && !needsFallback && !serverStt.isRecording) || (!studentSafe(voice) && !needsFallback)}
            aria-label={micLabel}
          >
            {stopActive ? <span className="stop-sq"></span> : <IconMic size={28} />}
          </button>

          <button type="button" className="v-end" onClick={() => { voice.stop(); onClose() }} aria-label={ui.voiceEnd}>
            <IconStop size={15} />
            <span className="v-end-label">{ui.voiceEnd}</span>
          </button>
        </div>
      </footer>
    </div>
  )
  // Portal to <body> so the live surface truly fills the app viewport and the
  // Copilot chat / dashboard can never bleed through.
  return typeof document === 'undefined' ? surface : createPortal(surface, document.body)
}

// Guard-local helper: the mic/stop control stays usable when the engine has an
// error so the user can retry (starts a fresh session from idle), but is locked
// only when speech recognition cannot run at all.
function studentSafe(voice: VoiceSessionApi): boolean {
  return !voice.error || voice.state === 'idle'
}
