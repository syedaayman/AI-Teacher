/**
 * Browser-Native Speech Synthesis (TTS) Service
 * Encapsulates Web Speech API (window.speechSynthesis) with support for
 * English, Hindi, and Hinglish, voice selection heuristics, speech controls,
 * and graceful fallback for unsupported browsers.
 */

class TTSService {
  constructor() {
    this.synth = typeof window !== 'undefined' && 'speechSynthesis' in window ? window.speechSynthesis : null;
    this.voices = [];
    this.currentUtterance = null;
    this.activeVoice = null;
    this._initialized = false;
    this._voicesLoadedPromise = null;

    if (this.synth) {
      this._initVoices();
    }
  }

  /**
   * Check if Web Speech API is supported in the current browser environment.
   * @returns {boolean}
   */
  isSupported() {
    return Boolean(this.synth && typeof window !== 'undefined' && 'SpeechSynthesisUtterance' in window);
  }

  /**
   * Initialize and cache browser voices, listening for voiceschanged event.
   * @private
   */
  _initVoices() {
    if (!this.synth) return;

    this._voicesLoadedPromise = new Promise((resolve) => {
      const load = () => {
        try {
          const list = this.synth.getVoices();
          if (list && list.length > 0) {
            this.voices = list;
            this._initialized = true;
            resolve(this.voices);
          }
        } catch (e) {
          console.warn('[TTSService] Failed to load voices:', e);
          resolve([]);
        }
      };

      load();

      if (typeof this.synth.addEventListener === 'function') {
        this.synth.addEventListener('voiceschanged', load);
      } else if ('onvoiceschanged' in this.synth) {
        this.synth.onvoiceschanged = load;
      }

      // Timeout fallback in case voiceschanged never fires (e.g., in some headless or Firefox configs)
      setTimeout(() => {
        if (!this._initialized) {
          load();
          resolve(this.voices);
        }
      }, 500);
    });
  }

  /**
   * Asynchronously get all available voices once discovered.
   * @returns {Promise<SpeechSynthesisVoice[]>}
   */
  async getAvailableVoices() {
    if (!this.isSupported()) return [];
    if (this.voices.length > 0) return this.voices;
    if (this._voicesLoadedPromise) {
      return await this._voicesLoadedPromise;
    }
    return this.synth.getVoices() || [];
  }

  /**
   * Find the most appropriate voice for English, Hindi, or Hinglish.
   * Heuristic priority:
   * - english: en-IN (Indian English) -> en-US -> en-GB -> any 'en'
   * - hindi: hi-IN -> any 'hi' -> en-IN -> default
   * - hinglish: en-IN -> hi-IN -> en-US -> default
   *
   * @param {'english'|'hindi'|'hinglish'} language
   * @returns {SpeechSynthesisVoice|null}
   */
  getVoiceForLanguage(language = 'english') {
    if (!this.isSupported()) return null;
    if (this.voices.length === 0 && this.synth) {
      try {
        const fresh = this.synth.getVoices();
        if (fresh && fresh.length > 0) {
          this.voices = fresh;
        }
      } catch (e) {
        // ignore
      }
    }
    if (this.voices.length === 0) return null;

    const normLang = (language || '').toLowerCase().trim();

    if (normLang === 'hindi') {
      const hindiVoice = this.voices.find(
        (v) => v.lang === 'hi-IN' || v.lang.toLowerCase().startsWith('hi')
      );
      if (hindiVoice) return hindiVoice;
      // Fallback for Hindi if native Hindi voice absent: use Indian English
      const fallbackIndian = this.voices.find(
        (v) => v.lang === 'en-IN' || v.lang.toLowerCase().startsWith('en-in')
      );
      if (fallbackIndian) return fallbackIndian;
    } else if (normLang === 'hinglish') {
      // For Hinglish, Indian English voice provides natural accentuation for hybrid phrases
      const indianVoice = this.voices.find(
        (v) => v.lang === 'en-IN' || v.lang.toLowerCase().startsWith('en-in')
      );
      if (indianVoice) return indianVoice;

      const hindiVoice = this.voices.find(
        (v) => v.lang === 'hi-IN' || v.lang.toLowerCase().startsWith('hi')
      );
      if (hindiVoice) return hindiVoice;
    }

    // Default / English path:
    // 1. en-IN (educational tone)
    const enIn = this.voices.find((v) => v.lang === 'en-IN');
    if (enIn) return enIn;

    // 2. High-quality neural or natural English voice
    const naturalEn = this.voices.find(
      (v) => v.lang.startsWith('en') && (v.name.includes('Natural') || v.name.includes('Neural') || v.name.includes('Google') || v.name.includes('Samantha'))
    );
    if (naturalEn) return naturalEn;

    // 3. en-US or en-GB
    const standardEn = this.voices.find(
      (v) => v.lang === 'en-US' || v.lang === 'en-GB' || v.lang.startsWith('en')
    );
    if (standardEn) return standardEn;

    // 4. Fallback to default
    return this.voices.find((v) => v.default) || this.voices[0] || null;
  }

  /**
   * Clean speech text by stripping markdown symbols and code blocks
   * so pronunciation is natural and conversational.
   * @param {string} text
   * @returns {string}
   */
  prepareTextForSpeech(text) {
    if (!text || typeof text !== 'string') return '';

    return text
      // Remove code blocks
      .replace(/```[\s\S]*?```/g, ' [Code implementation shown on blackboard] ')
      // Remove inline code
      .replace(/`([^`]+)`/g, '$1')
      // Remove markdown bold / italic markers
      .replace(/[*_~]{1,3}/g, '')
      // Remove markdown headers
      .replace(/^#{1,6}\s+/gm, '')
      // Remove bullet marks
      .replace(/^[\s*-+]{1,3}\s+/gm, '')
      // Normalize whitespace
      .replace(/\s+/g, ' ')
      .trim();
  }

  /**
   * Speak instructional narrative through Web Speech API.
   *
   * @param {string} text - Raw instructional narrative from Member 1
   * @param {Object} [options]
   * @param {'english'|'hindi'|'hinglish'} [options.language='english']
   * @param {number} [options.rate=1.0] - Speech rate (0.8 - 1.2)
   * @param {number} [options.pitch=1.0] - Pitch (0.9 - 1.1)
   * @param {Function} [options.onStart] - Callback when speech commences
   * @param {Function} [options.onEnd] - Callback when speech completes naturally
   * @param {Function} [options.onError] - Callback on error
   * @param {Function} [options.onPause] - Callback on pause
   * @param {Function} [options.onResume] - Callback on resume
   * @returns {boolean} Whether speech was successfully queued
   */
  speak(text, options = {}) {
    if (!this.isSupported()) {
      if (typeof options.onError === 'function') {
        options.onError(new Error('Web Speech API is not supported in this browser.'));
      }
      return false;
    }

    const cleanText = this.prepareTextForSpeech(text);
    if (!cleanText) {
      if (typeof options.onEnd === 'function') options.onEnd();
      return false;
    }

    // Cancel any ongoing speech immediately before starting new utterance
    this.cancel();

    try {
      const utterance = new window.SpeechSynthesisUtterance(cleanText);
      const voice = this.getVoiceForLanguage(options.language || 'english');

      if (voice) {
        utterance.voice = voice;
        utterance.lang = voice.lang;
        this.activeVoice = voice;
      } else {
        utterance.lang = options.language === 'hindi' ? 'hi-IN' : 'en-US';
      }

      utterance.rate = Math.max(0.8, Math.min(options.rate || 1.0, 1.4));
      utterance.pitch = Math.max(0.8, Math.min(options.pitch || 1.0, 1.2));

      utterance.onstart = () => {
        if (typeof options.onStart === 'function') options.onStart();
      };

      utterance.onend = () => {
        this.currentUtterance = null;
        if (typeof options.onEnd === 'function') options.onEnd();
      };

      utterance.onerror = (event) => {
        // 'interrupted' or 'canceled' are intentional stop events, not true errors
        if (event.error === 'interrupted' || event.error === 'canceled') {
          this.currentUtterance = null;
          return;
        }
        console.warn('[TTSService] Speech error:', event.error);
        this.currentUtterance = null;
        if (typeof options.onError === 'function') {
          options.onError(new Error(`Speech synthesis error: ${event.error}`));
        }
      };

      utterance.onpause = () => {
        if (typeof options.onPause === 'function') options.onPause();
      };

      utterance.onresume = () => {
        if (typeof options.onResume === 'function') options.onResume();
      };

      this.currentUtterance = utterance;
      if (typeof window !== 'undefined') {
        window._activeSpeechUtterance = utterance; // Prevents Chrome V8 GC bug
      }

      // Unfreeze Chrome synthesis queue if paused
      if (this.synth.paused) {
        this.synth.resume();
      }

      this.synth.speak(utterance);
      return true;
    } catch (err) {
      console.warn('[TTSService] Exception during speak():', err);
      this.currentUtterance = null;
      if (typeof options.onError === 'function') {
        options.onError(err);
      }
      return false;
    }
  }

  /**
   * Pause ongoing speech.
   */
  pause() {
    if (this.synth && this.synth.speaking && !this.synth.paused) {
      try {
        this.synth.pause();
      } catch (e) {
        console.warn('[TTSService] Failed to pause:', e);
      }
    }
  }

  /**
   * Resume paused speech.
   */
  resume() {
    if (this.synth && this.synth.paused) {
      try {
        this.synth.resume();
      } catch (e) {
        console.warn('[TTSService] Failed to resume:', e);
      }
    }
  }

  /**
   * Stop and cancel active speech.
   */
  cancel() {
    if (this.synth) {
      try {
        this.synth.cancel();
      } catch (e) {
        console.warn('[TTSService] Failed to cancel:', e);
      }
    }
    this.currentUtterance = null;
  }

  /**
   * Check if speech is currently playing.
   * @returns {boolean}
   */
  isSpeaking() {
    return Boolean(this.synth && this.synth.speaking && !this.synth.paused);
  }

  /**
   * Check if speech is currently paused.
   * @returns {boolean}
   */
  isPaused() {
    return Boolean(this.synth && this.synth.paused);
  }
}

// Export singleton instance
export const ttsService = new TTSService();
export default ttsService;
