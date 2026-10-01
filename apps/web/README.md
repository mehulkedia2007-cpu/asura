# DAARI web

The web app has English, Telugu and Hindi routes for the shared path, leads, schemes and voice surfaces. The header microphone opens the agent panel on every product page. `/te/voice` is the Telugu rural entry point. The language toggle keeps the current route.

```bash
pnpm install --frozen-lockfile
pnpm dev
pnpm typecheck && pnpm lint && pnpm test && pnpm build
```

Run the API on port 8000 for all data-backed features, including voice. Set `DAARI_API_URL` if the HTTP API runs elsewhere. The browser opens `ws://localhost:8000/ws/voice` by default; set `NEXT_PUBLIC_WS_URL` to the API WebSocket origin if it differs. The API sends interim transcripts, a final transcript, verified text, source cards, sentence audio and hop timing. MediaRecorder needs a secure context or localhost. Typed questions and browser speech recognition provide an input fallback; browser speech synthesis handles TTS failure.

See [the demo guide](../../docs/DEMO.md) for startup and browser regression commands.

The font files in `fonts/` are committed and loaded locally, so a production build does not fetch fonts from Google.
