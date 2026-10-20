# Podcast to Cartoon

Open the Xcode project: `native/PodcastProcessor.xcodeproj`. It is a Mac and iPad app. In Xcode, choose My Mac or an iPad and press Run. Do not add features to the website.

The Episode tab is a 16:9 table and a live switcher. Wide shows the whole table. Each name is a close-up. Click one while the episode plays to cut, then Export switched MP4 writes that show. Drag a person, their mouth, or the room. Uncheck On to leave someone out. Mouth placement and where they sit are saved on that avatar.

## Download

1. Open [Actions](https://github.com/adamjyo/podcast-to-cartoon/actions).
2. Open the latest **Build Mac app** run.
3. Download **PodcastProcessor-macOS** and unzip `PodcastProcessor.app`.
4. The first time, right-click the app and choose **Open**. It is not notarized by Apple.

## Before the first episode

1. Create a free token at https://huggingface.co/settings/tokens
2. Accept the terms on https://huggingface.co/pyannote/speaker-diarization-3.1 and https://huggingface.co/pyannote/segmentation-3.0
3. Paste the token into the app.
4. To draw avatars from headshots, paste your own xAI API key. The key stays on this Mac. Without it you can still keep the photo and use it as the puppet.

The first episode downloads speech models and needs the internet. Transcripts and videos land on the Desktop in `Podcast Processor`.


## Browser studio

The latest studio is in `web/`. Each person can have their own audio. The 16:9 table shows everyone who is turned on, mouths follow that audio, and you drag people, mouths, and the room. Mouth placement is saved with the avatar. **Export video** records the table.

```bash
cd web
npm install
npm run dev
```

`web/vite.mac.config.ts` builds the small double-click Mac wrapper in `web/mac`. The full Mac app is still the Python app from Actions.

## Native app for Mac and iPad

Open `native/PodcastProcessor.xcodeproj` in Xcode. Run it on My Mac or on an iPad. This one is a SwiftUI app, not the website and not the older Python app.

