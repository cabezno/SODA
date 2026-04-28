# Learnings from 888
*2026-04-25*

## Pattern: Decoupling Audio/DSP from Android UI
Separating audio capture (`Audio` module) and signal processing (`DSP` module) from the Android framework and UI proved highly effective. It makes the core pitch-detection logic (YIN algorithm) a pure, testable, and platform-agnostic unit, while isolating the platform-specific complexities of `AudioRecord` into a dedicated, reusable component.

## Pattern: Reactive Audio Stream with Kotlin Flow
Exposing the raw audio buffer from the `Audio` module as a Kotlin `Flow` is an excellent pattern for real-time processing. It allows the consumer (e.g., a ViewModel) to reactively and asynchronously handle incoming data, apply DSP transformations, and update the UI in a structured, non-blocking manner that integrates seamlessly with the modern Android stack.

## Pattern: Domain-Specific Algorithm Selection (YIN)
Choosing the YIN algorithm over a more generic FFT-based approach was a key decision for accuracy. YIN is specifically designed for fundamental frequency detection in monophonic signals, making it more robust against harmonics and noise for an application like a guitar tuner, balancing performance and precision on mobile hardware.

## Anti-pattern: Under-specced Profile for DSP
The initial `profile_general_dev` lacked the required `skill_audio_processing` and `skill_dsp`. While the project was successful, relying on generation to fill such a critical domain knowledge gap is risky. The profile should have been augmented first, as suggested by Copilot, to ensure the generated architecture and algorithms were based on a solid foundation of domain expertise.

## Preference: Multi-Module Clean Architecture
The architecture shows a clear preference for a highly modularized structure (Core, Data, Audio, DSP). This approach isolates responsibilities, improves testability, and keeps the core logic independent of the Android framework, which is a recurring pattern for building robust and maintainable applications.

## Preference: Modern Jetpack & Coroutines Stack
The choice of Jetpack DataStore for persistence and Kotlin Flow for data streaming indicates a strong preference for the modern, officially recommended Android development toolkit. This avoids legacy APIs (like SharedPreferences, AsyncTasks) in favor of more robust, asynchronous, and lifecycle-aware components.

## Preference: Encapsulation of Low-Level APIs
The `Audio` module acts as a facade over the complex and verbose Android `AudioRecord` API. This preference for encapsulating low-level, platform-specific details behind a clean, high-level interface (like a `Flow`) simplifies the rest of the application and improves code readability.

## Knowledge Suggestion
Pitch Detection Algorithms for Mobile: A comparative analysis of YIN, Autocorrelation, and FFT-based methods (e.g., Harmonic Product Spectrum) focusing on their trade-offs in terms of accuracy, computational cost, and robustness to noise for real-time applications on resource-constrained devices.
