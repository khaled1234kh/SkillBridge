// Framework-free SkillBridge voice-session engine.
//
// This module has ZERO React/DOM/browser imports so the exact state machine and
// orchestration (incl. barge-in, timeout, stop) can be unit-tested in Node with
// mocked recognition / TTS / HTTP / timers. The React hooks in
// `../hooks/useVoiceSession.ts` and `../hooks/useTTSPlayer.ts` only provide the
// real browser adapters and subscribe to notifications.
//
// Voice pipeline (ChatGPT-style): browser speech recognition -> existing
// POST /tutor -> existing POST /tutor/tts.
// The transcript is NEVER sent to /tutor/tts and audio is NEVER sent to /tutor.
import type { TutorLanguage } from './types'

export type VoiceState = 'idle' | 'listening' | 'processing' | 'speaking' | 'interrupted'

export type VoiceErrorKind = 'connection' | 'voice-unavailable' | 'mic'

export interface VoiceTranscriptItem {
  id: number
  role: 'user' | 'assistant'
  text: string
}

export type VoiceEvent =
  | { type: 'start' }
  | { type: 'speechFinal'; transcript: string }
  | { type: 'replyReady' }
  | { type: 'audioStart' }
  | { type: 'audioEnd' }
  | { type: 'bargeIn' }
  | { type: 'speakDuringProcessing' }
  | { type: 'interruptedTimeout' }
  | { type: 'stop' }
  | { type: 'error' }

// Exact transition table (task spec):
//   idle -> listening            (user taps the mic)
//   listening -> processing      (STT final result)
//   processing -> speaking       (/tutor reply in; TTS plays)
//   speaking -> idle             (TTS audio finished)
//   speaking -> interrupted      (speech heard while speaking, OR mic while speaking)
//   interrupted -> listening     (400 ms later)
//   processing -> listening      (speech heard while /tutor in flight — keep partial; abort fetch)
//   * -> idle                    (stop / error). Unlisted events are no-ops
//                               (e.g. "empty STT while speaking -> stay").
const ALLOWED: Record<VoiceState, { [K in VoiceEvent['type']]?: VoiceState }> = {
  idle: { start: 'listening' },
  listening: { speechFinal: 'processing', stop: 'idle', error: 'idle' },
  processing: {
    replyReady: 'speaking',
    audioStart: 'speaking',
    speakDuringProcessing: 'listening',
    stop: 'idle',
    error: 'idle',
  },
  speaking: { audioEnd: 'idle', bargeIn: 'interrupted', stop: 'idle', error: 'idle' },
  interrupted: { interruptedTimeout: 'listening', stop: 'idle', error: 'idle' },
}

export function reduceVoice(state: VoiceState, event: VoiceEvent['type']): VoiceState {
  const next = ALLOWED[state]?.[event]
  return next ?? state
}

/** Language tokens required by the browser speech recognizer. */
export function recognitionLang(language: TutorLanguage): string {
  if (language === 'ar') return 'ar-EG'
  return 'en-US'
}

/** Recognizer adapter the engine drives (wraps `SpeechRecognition` in the hook). */
export interface SpeechRecognitionAdapter {
  hush(): void
  listen(opts: {
    mode: 'primary' | 'interrupt'
    lang: string
    onFinal?(transcript: string): void
    onSpeechStart?(): void
    onError?(errorType?: string): void
  }): void
}

/** Audio handle returned by the TTS adapter. `done` resolves on natural end. */
export interface PlaybackHandle {
  stop(): void
  done: Promise<void>
}

/** TTS adapter the engine drives (wraps api.tutorTts + `new Audio()` in the hook). */
export interface VoiceTtsAdapter {
  synthesize(text: string, signal: AbortSignal): Promise<unknown>
  play(payload: unknown): PlaybackHandle
}

export interface VoiceSessionAdapters {
  recognition: SpeechRecognitionAdapter
  tts?: VoiceTtsAdapter
  /**
   * POST /tutor adapter. Returns the assistant reply text. `opts.language` is
   * the explicit Live speech language ('en' | 'ar') the caller should send so
   * the backend replies in the same language. Live Voice has NO Auto mode: the
   * user picks English or Arabic explicitly, and the recognizer locale never
   * switches on its own.
   */
  send(text: string, signal: AbortSignal, opts?: { language?: 'en' | 'ar' }): Promise<string>
  schedule(cb: () => void, ms: number): number
  cancelSchedule(id: number): void
}

export interface VoiceSessionOptions {
  /**
   * Hard guard on the /tutor reply. The backend bounds provider timeouts and
   * the UI spec adds a small buffer around the live backend default.
   */
  replyTimeoutMs?: number
  /** Interrupted -> listening handoff delay (spec: 400 ms). */
  interruptedDelayMs?: number
  /**
   * Hands-free mode (Phase 4B.1 Live): after a TTS turn naturally finishes
   * (audioEnd -> idle) the engine automatically returns to listening and starts
   * a fresh primary recognizer, so the user never taps the mic per turn.
   * Fire only for a clean audio end — stop / error / TTS-unavailable never resume.
   */
  resumeAfterPlaybackEnd?: boolean
  /** Small pause before the automatic listening resume (idle flash avoided). */
  resumeDelayMs?: number
  /**
   * The explicit Live speech language ('en' | 'ar'). Live Voice has TWO speech
   * modes and NO Auto inside the session: browser SpeechRecognition is
   * single-locale per instance, so the user selects English or Arabic and the
   * recognizer locale is fixed to it for the whole listening session.
   */
  language: 'en' | 'ar'
  /**
   * Server-STT-only mode (Brave): never start a browser SpeechRecognition —
   * Brave cannot reach Google's speech servers, so the recognizer hangs or
   * loops on empty errors. Turns are driven entirely through
   * `injectTranscript()` from the VoiceMode push-to-talk recorder.
   */
  skipBrowserStt?: boolean
  /** Fires whenever the Live speech language changes (initial + on switch), so
   *  the UI can mirror direction and captions live. */
  onLanguageDetected?(lang: 'en' | 'ar'): void
  onState(state: VoiceState): void
  onTranscript(item: VoiceTranscriptItem): void
  onError(kind: VoiceErrorKind, message: string): void
  onAssistantReply?(reply: string): void
  /**
   * Developer diagnostics: structured stage + safe meta (no transcripts, keys or
   * secret values). Fires at every Live-pipeline decision point so a silent
   * mentor can be traced to the exact stage that failed.
   */
  onTrace?: (stage: string, meta?: Record<string, unknown>) => void
  /**
   * Hold-off after submitting a turn: ignore speech-start barge-ins from the
   * interrupt recognizer for this many ms to avoid aborting the fresh turn on
   * residual VAD/echo from the just-ended utterance. Default 500 ms (0 in test).
   */
  bargeInHoldOffMs?: number
}

const DEFAULT_REPLY_TIMEOUT_MS = 65_000
const DEFAULT_INTERRUPTED_DELAY_MS = 400
const DEFAULT_RESUME_DELAY_MS = 150
const DEFAULT_BARGE_IN_HOLD_OFF_MS = 500
/** If the browser SpeechRecognition has been in 'listening' state for this long
 *  without producing any interim or final result, we assume the STT backend is
 *  unreachable (e.g. Brave blocking Google's speech servers) and auto-trigger
 *  the server-side STT fallback. */
const LISTENING_DEADLOCK_MS = 8_000
/** Consecutive non-fatal recognizer errors (no-speech / aborted) with ZERO
 *  interim or final results that also signal a broken STT backend. After this
 *  many, we give up on browser STT and activate the fallback. */
const MAX_EMPTY_ERRORS = 3

export class VoiceSession {
  state: VoiceState = 'idle'
  transcript: VoiceTranscriptItem[] = []

  private readonly adapters: VoiceSessionAdapters
  private readonly opts: VoiceSessionOptions
  private readonly replyTimeoutMs: number
  private readonly interruptedDelayMs: number
  private readonly resumeDelayMs: number
private itemId = 1
  /** Guards the async /tutor -> TTS reply pipeline (stop/clear/barge-in abort it). */
  private sessionId = 0
  /** Per-listen recognition generation snapshots callbacks that went stale
   *  (superseded by interrupt, barge-in, stop, clear or a mid-session language
   *  switch). Independent of `sessionId`, which guards the async /tutor->TTS
   *  reply pipeline -- starting the interrupt recognizer must NOT cancel the
   *  in-flight reply. */
  private recogId = 0
  /** Explicit Live speech language ('en' | 'ar') — the CURRENT recognizer
   *  locale. Set on construction, on user switch (immediately when safe), and
   *  applied after the current turn finishes when a switch arrived while the
   *  mentor was speaking or /tutor was in flight. Never detected: Live Voice
   *  has no Auto mode. */
  private sessionLang: 'en' | 'ar'
  /** The language used by the CURRENT utterance (sent to /tutor). */
  private turnLang: 'en' | 'ar'
  /** A language switch requested while speaking/processing, applied when the
   *  loop returns to listening (playback is never cut for a language change). */
  private pendingLang: 'en' | 'ar' | null = null
  private sendAbort: AbortController | null = null
  private ttsAbort: AbortController | null = null
  private playback: PlaybackHandle | null = null
  private timeoutId: number | null = null
  private interruptId: number | null = null
  private resumeId: number | null = null
  /** Detect a dead browser SpeechRecognition: while 'listening', if no interim
   *  or final result arrives within LISTENING_DEADLOCK_MS we assume the STT
   *  service is unreachable (Brave) and switch to the server-side fallback. */
  private listenDeadlockId: number | null = null
  /** Consecutive non-fatal errors (no-speech/aborted) with no results at all. */
  private emptyErrors = 0
  /** Configured hold-off duration (0 in test, 500 ms in browser). */
  private readonly bargeInHoldOffMs: number
  /** Timestamp until which speech-start barge-ins from the interrupt recognizer are ignored. */
  private bargeInHoldOffUntil = 0
  /** Per-utterance latency clock (Phase 4C.1). Zeroed at each STT final; every
   *  spoken-turn stage traces `elapsedMs` from that moment. Developer trace only
   *  (never shown in the UI, never a secret). */
  private turnStartMs = 0
  /** Wall-clock of the last /tutor/tts payload readiness (for playDelayMs). */
  private ttsReadyAtMs = 0

  constructor(adapters: VoiceSessionAdapters, opts: VoiceSessionOptions) {
    this.adapters = adapters
    this.opts = opts
    this.replyTimeoutMs = opts.replyTimeoutMs ?? DEFAULT_REPLY_TIMEOUT_MS
    this.interruptedDelayMs = opts.interruptedDelayMs ?? DEFAULT_INTERRUPTED_DELAY_MS
    this.resumeDelayMs = opts.resumeDelayMs ?? DEFAULT_RESUME_DELAY_MS
    // In Node.js (test env) disable the hold-off so synchronous contract tests pass;
    // in the browser the 500 ms hold-off prevents echo-flap aborts.
    const isNode = typeof window === 'undefined'
    this.bargeInHoldOffMs = opts.bargeInHoldOffMs ?? (isNode ? 0 : DEFAULT_BARGE_IN_HOLD_OFF_MS)
    this.sessionLang = opts.language === 'ar' ? 'ar' : 'en'
    this.turnLang = this.sessionLang
    this.pendingLang = null
  }

  get error(): string | null {
    return this.currentError
  }

  private currentError: string | null = null

  private trace(stage: string, meta?: Record<string, unknown>): void {
    this.opts.onTrace?.(stage, meta)
  }

  /** Milliseconds since the current utterance's STT final (0 before any turn). */
  private elapsedMs(): number {
    return this.turnStartMs ? Date.now() - this.turnStartMs : 0
  }

  clear(): void {
    this.voidPending()
    this.transcript = []
    this.currentError = null
    this.transition('stop')
  }

  start(): void {
    if (this.state !== 'idle') return
    this.currentError = null
    this.applyPendingLang()
    if (this.opts.skipBrowserStt) {
      // Server-STT-only mode (Brave): no browser recognizer. VoiceMode's
      // push-to-talk recorder drives every turn through injectTranscript(),
      // so the session simply waits in the idle state for those injections.
      this.trace('stt.server_mode', {})
      return
    }
    this.transition('start')
    this.listenPrimary()
  }

  /** Orbig keyboard/stop: behaves exactly like the spec's barge-in when speaking. */
  stop(): void {
    this.voidPending()
    this.transition('stop')
  }

  /**
   * Switch the explicit Live speech language (EN | عربي) mid-session.
   * SAFE SWITCH BEHAVIOR (documented):
   *  - listening  -> hush the current recognizer, invalidate its stale
   *                  callbacks (recogId bump), restart Listening in the new
   *                  locale. Never two recognizers, never a stale final commit.
   *  - idle/interrupted -> apply immediately (nothing is in flight).
   *  - processing /speaking -> the switch is NOT improvised mid-turn: the
   *                  in-flight /tutor stays in the old language and mentor TTS
   *                  is NEVER cut by a language change. `pendingLang` is applied
   *                  right before the next Listening starts (after playback / on
   *                  barge-in handoff), so the loop continues in the new locale.
   */
  setLanguage(lang: 'en' | 'ar'): void {
    const target = lang === 'ar' ? 'ar' : 'en'
    if (target === this.sessionLang && !this.pendingLang) return
    this.trace('lang.set', { to: target, state: this.state })
    switch (this.state) {
      case 'idle':
      case 'interrupted':
        this.sessionLang = target
        this.pendingLang = null
        this.opts.onLanguageDetected?.(target)
        break
      case 'listening':
        this.recogId += 1
        this.adapters.recognition.hush()
        this.sessionLang = target
        this.pendingLang = null
        this.listenPrimary()
        this.opts.onLanguageDetected?.(target)
        break
      default:
        // processing / speaking: apply when the loop returns to listening.
        this.pendingLang = target
    }
  }

  /** Apply a switch that arrived while a turn was in flight, right before the
   *  next Listening session starts. */
  private applyPendingLang(): void {
    if (!this.pendingLang) return
    const target = this.pendingLang
    this.pendingLang = null
    this.sessionLang = target
    this.opts.onLanguageDetected?.(target)
    this.trace('lang.applied', { to: target })
  }

  private listenPrimary(): void {
    // Server-STT-only mode (Brave): NEVER start the browser recognizer, even on
    // an interrupted-handoff or processing-barge-in path — `start()` is not the
    // only entry point, and re-opening the broken recognizer after an interrupt
    // knocks Live back into the voice-unavailable error state. The entry is a
    // no-op that keeps the state machine parked at 'listening', which VoiceMode
    // drives entirely through injectTranscript().
    if (this.opts.skipBrowserStt) {
      this.trace('stt.server_mode', { from: 'listenPrimary' })
      return
    }
    const recogId = ++this.recogId
    this.armListenDeadlock()
    this.adapters.recognition.listen({
      mode: 'primary',
      lang: recognitionLang(this.sessionLang),
      onFinal: (text) => {
        if (this.recogId !== recogId) return
        this.handlePrimaryFinal(text)
      },
      onSpeechStart: () => {
        if (this.recogId !== recogId) return
        this.bargeIn()
      },
      onError: (errorType?: string) => {
        if (this.recogId !== recogId) return
        if (this.state !== 'listening') return
        // 'no-speech' and 'aborted' are non-fatal — recognition will restart
        // naturally via onend. But if the recognizer NEVER produces a single
        // result and only loops on these, the STT backend is broken (Brave).
        // After MAX_EMPTY_ERRORS we give up on browser STT for the session.
        if (errorType === 'no-speech' || errorType === 'aborted') {
          this.emptyErrors += 1
          this.trace('stt.nonfatal', { errorType, emptyErrors: this.emptyErrors })
          if (this.emptyErrors >= MAX_EMPTY_ERRORS) {
            this.sttUnavailable('Speech recognition is not working in this browser — switching to server transcription')
          }
          return
        }
        if (errorType === 'network') {
          this.sttUnavailable('Speech service unavailable — using server transcription')
        } else {
          this.currentError = 'Microphone permission required'
          this.opts.onError('mic', this.currentError)
        }
        this.transition('error')
        this.transition('stop')
      },
    })
  }

  /** Assume browser STT is broken (Brave): surface the honest error and stop,
   *  which lets VoiceMode switch the mic into server-STT push-to-talk mode. */
  private sttUnavailable(message: string): void {
    if (this.currentError || this.state !== 'listening') return
    this.currentError = message
    this.opts.onError('voice-unavailable', this.currentError)
    this.trace('stt.fallback_triggered', { reason: message })
    this.transition('error')
    this.transition('stop')
  }

  /** While 'listening', if no recognition result arrives within
   *  LISTENING_DEADLOCK_MS we assume the STT backend cannot be reached and
   *  activate the server fallback. */
  private armListenDeadlock(): void {
    this.disarmListenDeadlock()
    this.listenDeadlockId = this.adapters.schedule(() => {
      this.listenDeadlockId = null
      if (this.state === 'listening') {
        this.trace('stt.deadlock', { timeoutMs: LISTENING_DEADLOCK_MS, emptyErrors: this.emptyErrors })
        this.sttUnavailable('Speech recognition is not responding — holding the mic uses server transcription')
      }
    }, LISTENING_DEADLOCK_MS)
  }

  private disarmListenDeadlock(): void {
    if (this.listenDeadlockId != null) {
      this.adapters.cancelSchedule(this.listenDeadlockId)
      this.listenDeadlockId = null
    }
  }

  /** Any real progress (interim/final) resets the deadlock clock + error count. */
  private bumpListenProgress(): void {
    this.emptyErrors = 0
    this.armListenDeadlock()
  }

  private listenInterrupt(): void {
    const recogId = ++this.recogId
    this.adapters.recognition.listen({
      mode: 'interrupt',
      lang: recognitionLang(this.sessionLang),
      // STT while the tutor is speaking: any final (incl. empty) leaves the
      // speaking state untouched — only *starting* to speak triggers the
      // barge-in (see onSpeechStart). No transcript event here.
      onFinal: () => {},
      onSpeechStart: () => {
        if (this.recogId !== recogId) return
        // Ignore speech-start during the hold-off window to avoid aborting the
        // freshly submitted turn on residual VAD/echo from the just-ended utterance.
        if (Date.now() < this.bargeInHoldOffUntil) {
          this.trace('bargein.holdoff', { from: 'interrupt', remainingMs: this.bargeInHoldOffUntil - Date.now() })
          return
        }
        this.bargeIn()
      },
      onError: () => {
        if (this.recogId !== recogId) return
        // Interrupt recognizer errors are always non-fatal — the primary
        // listener or the stop button will handle the real outcome.
        this.trace('stt.interrupt_error', {})
      },
    })
  }

  private handlePrimaryFinal(text: string): void {
    if (this.state !== 'listening') {
      this.trace('submit.guard', { state: this.state })
      return
    }
    const userText = text.trim()
    if (!userText) return
    this.currentError = null
    this.disarmListenDeadlock()
    this.emptyErrors = 0
    // Explicit Live speech language for this utterance (the selected locale),
    // reported so the UI can mirror direction/captions for the turn.
    this.turnLang = this.sessionLang
    this.turnStartMs = Date.now()
    this.ttsReadyAtMs = 0
    this.opts.onLanguageDetected?.(this.turnLang)
    this.trace('lang.detect', { lang: this.turnLang })
    this.trace('stt.final', { chars: userText.length, elapsedMs: 0 })
    this.adapters.recognition.hush()
    this.appendTranscript('user', userText)
    this.transition('speechFinal')
    // Keep an interrupt recognizer while /tutor is in flight so a REAL speech
    // start (VAD) can barge in and abort the stale fetch (see the browser
    // adapter: only onSpeechStart maps to a barge-in — noise finals never do).
    this.listenInterrupt()
    // Ignore any speech-start barge-in for a short window to avoid aborting the
    // freshly submitted turn on residual VAD/echo from the just-ended utterance.
    this.bargeInHoldOffUntil = Date.now() + this.bargeInHoldOffMs
    this.reply(userText)
  }

  /**
   * Inject a transcript from server-side STT (used when the browser Speech
   * API is unavailable, e.g. Brave). Behaves identically to handlePrimaryFinal
   * but skips the browser recognition hush — the recording was already stopped.
   * A new dictated turn WINS over an in-flight /tutor reply or mentor playback:
   * the stale reply/audio is dropped and the fresh turn is submitted (same as
   * a deliberate barge-in, but with a real recognized utterance to send).
   */
  injectTranscript(text: string): void {
    const userText = text.trim()
    if (!userText) return
    if (this.state === 'speaking' || this.state === 'interrupted') {
      // stop mentor audio; the new turn replaces it.
      this.recogId += 1
      this.adapters.recognition.hush()
      this.ttsAbort?.abort()
      this.ttsAbort = null
      this.playback?.stop()
      this.playback = null
      this.disarmResume()
      this.sessionId += 1
      this.transition('stop')
      this.trace('inject.bargein', { from: this.state })
    } else if (this.state === 'processing') {
      // abort the in-flight /tutor; the new dictated turn is submitted instead.
      this.sessionId += 1
      this.sendAbort?.abort()
      this.sendAbort = null
      this.disarmTimeout()
      this.transition('speakDuringProcessing')
      this.trace('inject.bargein', { from: 'processing' })
    }
    if (this.state !== 'listening' && this.state !== 'idle') {
      this.trace('inject.guard', { state: this.state })
      return
    }
    this.currentError = null
    this.disarmListenDeadlock()
    this.emptyErrors = 0
    this.turnLang = this.sessionLang
    this.turnStartMs = Date.now()
    this.ttsReadyAtMs = 0
    this.opts.onLanguageDetected?.(this.turnLang)
    this.trace('stt.server_final', { chars: userText.length, elapsedMs: 0 })
    this.appendTranscript('user', userText)
    if (this.state === 'idle') this.transition('start')
    this.transition('speechFinal')
    this.reply(userText)
  }

  /**
   * Wait for /tutor (with the hard timeout) then synth + play /tutor/tts.
   * CRITICAL for hands-free Live: from replyReady onward the microphone is
   * FULLY hushed — the mentor's own speaker audio can never be mistaken for a
   * user barge-in, so playback always reaches its natural `ended`. Deliberate
   * interruption is still available via the mic/orb button (VoiceMode routes
   * speaking/processing taps through `interrupt()`/`stop()`).
   */
  private async reply(userText: string): Promise<void> {
    const session = this.sessionId
    this.sendAbort = new AbortController()
    this.armTimeout()
    this.trace('tutor.sent', { lang: this.turnLang, elapsedMs: this.elapsedMs() })
    let reply: string
    try {
      reply = await this.adapters.send(userText, this.sendAbort.signal, { language: this.turnLang })
    } catch (err) {
      if (this.sessionId !== session) return
      if (this.sendAbort?.signal.aborted) return
      this.disarmTimeout()
      if (this.state === 'idle') return
      this.currentError = 'Connection lost — try again'
      this.trace('tutor.error', { kind: 'fetch', status: (err as { status?: number })?.status ?? null, lang: this.turnLang, elapsedMs: this.elapsedMs() })
      this.transition('error')
      this.transition('stop')
      this.opts.onError('connection', this.currentError)
      return
    }
    if (this.sessionId !== session) return
    this.disarmTimeout()
    this.currentError = null
    this.trace('tutor.ok', { chars: reply.length, lang: this.turnLang, elapsedMs: this.elapsedMs() })
    this.transition('replyReady')
    // A UI-side chat-thread handler must never be able to kill the spoken
    // reply pipeline: it runs after the turn is already 'speaking'. Any error
    // it throws is swallowed (with a trace) so synthesizing still proceeds.
    try {
      this.opts.onAssistantReply?.(reply)
    } catch (err) {
      this.trace('reply.assistant_callback_error', { kind: (err as { name?: string })?.name ?? 'Error' })
    }
    await this.speakReply(reply, session)
  }

  private async speakReply(reply: string, session: number): Promise<void> {
    const tts = this.adapters.tts
    if (!tts) {
      this.appendTranscript('assistant', reply)
      this.transition('stop')
      this.currentError = 'Voice unavailable'
      this.trace('tts.error', { kind: 'no-adapter' })
      this.opts.onError('voice-unavailable', this.currentError)
      return
    }
    this.appendTranscript('assistant', reply)
    // No recognizer while the mentor speaks (see class doc above).
    this.adapters.recognition.hush()
    this.ttsAbort = new AbortController()
    this.trace('tts.sent', { chars: reply.length, lang: this.turnLang, elapsedMs: this.elapsedMs() })
    let payload: unknown
    try {
      payload = await tts.synthesize(reply, this.ttsAbort.signal)
    } catch (err) {
      if (this.sessionId !== session) return
      this.trace('tts.error', { kind: 'synth', status: (err as { status?: number })?.status ?? null, lang: this.turnLang, elapsedMs: this.elapsedMs() })
      this.transition('stop')
      this.currentError = 'Voice unavailable'
      this.opts.onError('voice-unavailable', this.currentError)
      return
    }
    if (this.sessionId !== session) return
    if (this.state !== 'speaking' && this.state !== 'processing') return
    if (this.state !== 'speaking') this.transition('replyReady')
    this.trace('tts.ok', { lang: this.turnLang, elapsedMs: this.elapsedMs() })
    this.ttsReadyAtMs = Date.now()
    let handle: PlaybackHandle
    try {
      handle = tts.play(payload)
    } catch {
      this.trace('tts.error', { kind: 'play-setup', lang: this.turnLang, elapsedMs: this.elapsedMs() })
      this.transition('stop')
      this.currentError = 'Voice unavailable'
      this.opts.onError('voice-unavailable', this.currentError)
      return
    }
    this.playback = handle
    this.transition('audioStart')
    this.trace('play.start', { chars: reply.length, lang: this.turnLang, elapsedMs: this.elapsedMs(), playDelayMs: this.ttsReadyAtMs ? Date.now() - this.ttsReadyAtMs : 0 })
    handle.done.then(() => {
      if (this.sessionId !== session) return
      this.trace('play.end')
      this.transition('audioEnd')
      // Hands-free loop: a clean natural end returns to listening by itself.
      if (this.opts.resumeAfterPlaybackEnd) this.scheduleResume()
    })
  }

  /** Auto-listening resume after a completed spoken turn (hands-free). */
  private scheduleResume(): void {
    this.disarmResume()
    this.resumeId = this.adapters.schedule(() => {
      this.resumeId = null
      // Only a clean audio end resumes: stop/error/TTS-unavailable left an error
      // or a different state, and the user must explicitly retry there.
      if (this.state === 'idle' && !this.currentError) {
        this.trace('resume.fired')
        this.adapters.recognition.hush()
        this.applyPendingLang()
        this.start()
      }
    }, this.resumeDelayMs)
    this.trace('resume.scheduled', { delayMs: this.resumeDelayMs })
  }

  private disarmResume(): void {
    if (this.resumeId != null) {
      this.adapters.cancelSchedule(this.resumeId)
      this.resumeId = null
    }
  }

  private bargeIn(): void {
    if (this.state === 'speaking') {
      this.trace('bargein', { from: 'speaking' })
      this.recogId += 1
      this.adapters.recognition.hush()
      this.ttsAbort?.abort()
      this.trace('play.abort', {})
      this.playback?.stop()
      this.playback = null
      // Keep the partial transcript; never send audio/transcript anywhere.
      this.transition('bargeIn')
      this.scheduleInterruptedHandoff()
    } else if (this.state === 'processing') {
      // Speech heard while /tutor is in flight: abort the fetch, keep the
      // partial transcript, and go straight back to listening.
      this.trace('bargein', { from: 'processing' })
      this.sessionId += 1
      this.recogId += 1
      this.adapters.recognition.hush()
      this.sendAbort?.abort()
      this.sendAbort = null
      this.disarmTimeout()
      this.transition('speakDuringProcessing')
      this.applyPendingLang()
      this.listenPrimary()
    }
  }

  /** User action equivalent of hearing speech (mic tap while speaking). */
  interrupt(): void {
    this.bargeIn()
  }

  private armTimeout(): void {
    this.disarmTimeout()
    this.timeoutId = this.adapters.schedule(() => {
      if (this.state === 'processing') {
        this.sendAbort?.abort()
        this.disarmTimeout()
        this.currentError = 'Connection lost — try again'
        this.transition('error')
        this.transition('stop')
        this.opts.onError('connection', this.currentError)
      }
    }, this.replyTimeoutMs)
  }

  private disarmTimeout(): void {
    if (this.timeoutId != null) {
      this.adapters.cancelSchedule(this.timeoutId)
      this.timeoutId = null
    }
  }

  private appendTranscript(role: 'user' | 'assistant', text: string): void {
    const item: VoiceTranscriptItem = { id: this.itemId++, role, text }
    this.transcript = [...this.transcript, item]
    this.opts.onTranscript(item)
  }

  private voidPending(): void {
    this.sessionId += 1
    this.recogId += 1
    this.adapters.recognition.hush()
    this.sendAbort?.abort()
    this.sendAbort = null
    this.ttsAbort?.abort()
    this.ttsAbort = null
    this.playback?.stop()
    this.playback = null
    this.disarmTimeout()
    this.disarmInterrupt()
    this.disarmResume()
    this.disarmListenDeadlock()
  }

  private transition(event: VoiceEvent['type']): void {
    const next = reduceVoice(this.state, event)
    if (next !== this.state) {
      this.state = next
      this.opts.onState(next)
    }
    if (event === 'start' || event === 'interruptedTimeout') {
      // handled by the caller (listenPrimary / listenPrimary after the delay)
    }
  }

  private interruptedHandoff(): void {
    if (this.state !== 'interrupted') return
    this.transition('interruptedTimeout')
    this.applyPendingLang()
    this.listenPrimary()
  }

  private disarmInterrupt(): void {
    if (this.interruptId != null) {
      this.adapters.cancelSchedule(this.interruptId)
      this.interruptId = null
    }
  }

  // The interrupted -> 400 ms -> listening handoff.
  private scheduleInterruptedHandoff(): void {
    this.disarmInterrupt()
    this.interruptId = this.adapters.schedule(() => {
      this.interruptId = null
      this.interruptedHandoff()
    }, this.interruptedDelayMs)
  }
}
