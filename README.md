# Podcast to Cartoon

Mac app that takes a mixed podcast recording, separates about four or five speakers, lets you name each voice, and writes a simple hand-drawn style video with the mouth open on whoever is talking.

The downloadable app is built by GitHub Actions. You do not package it on your Mac.

## Download

1. Open the Actions tab: https://github.com/adamjyo/podcast-to-cartoon/actions
2. Open the latest **Build Mac app** run.
3. Download the **PodcastProcessor-macOS** artifact.
4. Unzip it. You get `PodcastProcessor.app`.
5. The first time, right-click the app and choose **Open**, then **Open** again. macOS does this because the app is not notarized by Apple.

## Before the first episode

1. Create a free token at https://huggingface.co/settings/tokens
2. Accept the terms on:
   - https://huggingface.co/pyannote/speaker-diarization-3.1
   - https://huggingface.co/pyannote/segmentation-3.0
3. Paste the token into the app. It is saved only on your Mac.

The first episode downloads speech models (a few GB) and needs an internet connection. After that, processing stays on your Mac. Finished files land on your Desktop in `Podcast Processor`.

The cartoon is a simple drawn cast (one card per voice, mouth open while that person talks), not a finished studio animation. Swap-in character art can come later.
