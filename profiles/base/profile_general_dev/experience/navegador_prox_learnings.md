# Learnings from navegador_prox
*2026-04-22*

## Pattern: Dual-Layer Resource Optimization
Combining passive optimization via browser launch flags (--disable-gpu, --single-process) with active optimization via request interception (blocking video/image formats) is a highly effective pattern for creating minimal-resource browsers. It provides comprehensive control over both engine behavior and network traffic.

## Pattern: Proxy Tunneling for Engine Compatibility
Using an intermediate library like 'proxy-chain' to create a local HTTP proxy that tunnels to the user's actual SOCKS/authenticated proxy is a robust solution. It abstracts away the complexities and inconsistencies of native proxy support in Chromium, simplifying the configuration passed to Playwright/Puppeteer.

## Pattern: Modular Browser Service Architecture
Separating concerns into distinct modules like ConfigStore, ProxyManager, and RequestLogger works very well for browser automation projects. This decouples the core browser logic from features like configuration and logging, making the system easier to maintain and extend.

## Anti-pattern: Using Electron for Minimal-Resource Goals
The choice of Electron for the UI directly conflicted with the core requirement of 'minimum resource consumption' due to its high baseline RAM usage. For projects where performance and low footprint are the primary drivers, a CLI or a lighter native webview wrapper should be the default choice over a full Chromium-based shell.

## Preference: High Configurability for Power Users
The design consistently favors providing granular user control (e.g., choosing the engine, detailed proxy settings, multiple video modes) over opinionated defaults. This indicates a preference for building flexible, powerful tools for a technical audience.

## Preference: Secure, Local-First Configuration
The decision to create a dedicated 'ConfigStore' module that encrypts the local 'config.json' file reveals a preference for secure-by-default handling of sensitive user data, such as proxy credentials.

## Knowledge Suggestion
For projects using Playwright/Puppeteer that require robust support for various proxy types (especially SOCKS4/5 with authentication), the `proxy-chain` npm package is a highly effective solution. It tunnels the connection through a local HTTP proxy, simplifying the arguments passed to Chromium and reliably handling complex authentication scenarios.
