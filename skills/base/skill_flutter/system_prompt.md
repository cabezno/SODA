## Skill: Flutter / Dart

You are building a Flutter application. Follow these conventions:

- Use Dart 3.x with null safety — all types non-nullable unless explicitly marked `?`
- State management with Riverpod 2.x (`@riverpod` codegen) or BLoC — never `setState` for app state
- Use `go_router` for navigation — not Navigator 1.0 push/pop
- Widgets split into: small reusable widgets in `widgets/`, full screens in `screens/` or `pages/`
- Models use `freezed` + `json_serializable` for immutability and JSON serialization
- Avoid `BuildContext` across async gaps — check `mounted` before using context after await
- `pubspec.yaml` defines all assets and fonts explicitly; wildcard `assets/` globs require Flutter >= 3.19
- `analysis_options.yaml` must include `flutter_lints` package rules
