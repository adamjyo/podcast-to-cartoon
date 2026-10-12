# Podcast to Cartoon

Mac app for a mixed podcast: it separates the speakers, keeps a cast of drawn avatars, and writes a cartoon whose mouths follow the recording.

Avatars are stored on your Mac in `~/Library/Application Support/PodcastProcessor/cast`. Add a headshot once, draw it, and reuse that person on the next episode. Mouth timing comes from [Rhubarb Lip Sync](https://github.com/DanielSWolf/rhubarb-lip-sync), which is bundled in the app.

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
