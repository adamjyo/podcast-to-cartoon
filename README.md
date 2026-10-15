# Podcast to Cartoon

Mac app for a mixed podcast: it separates the speakers, keeps a cast of drawn avatars, and writes a cartoon whose mouths follow the recording.

The Puppet tab places each mouth and sets how big that person stands. The Set tab picks a room, or draws one from a short description. Both are saved on this Mac and reused on the next episode. Avatars live in `~/Library/Application Support/PodcastProcessor/cast`, sets in `backgrounds` beside that. Mouth timing comes from [Rhubarb Lip Sync](https://github.com/DanielSWolf/rhubarb-lip-sync), which is bundled in the app.

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

The latest studio is in `web/`. The page scrolls, a line plays with a speech-like jaw, and **Export video** downloads a short clip of the face talking.

```bash
cd web
npm install
npm run dev
```
