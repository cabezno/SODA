## Skill: React Native

You are building a React Native application. Follow these conventions:

- Use TypeScript throughout — all files `.tsx` (with JSX) or `.ts` (logic only)
- Prefer Expo SDK 51+ (managed or bare workflow) — faster setup, OTA updates, EAS Build
- Navigation with `@react-navigation/native` + stack/tab navigators
- State management with Zustand or Redux Toolkit — avoid Context for large app state
- Styling with StyleSheet.create() — no inline styles in JSX
- Environment variables via `react-native-dotenv` or Expo's `Constants.expoConfig.extra`
- Platform-specific code via `Platform.OS === 'ios'` or `.ios.ts` / `.android.ts` file extensions
- `metro.config.js` required for module resolution customization
