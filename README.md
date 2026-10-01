# ALFRED 🦇

A voice-powered personal assistant powered by Claude (Anthropic), with the manners of a British butler.
Say **"Alfred"** followed by your request and he answers out loud and takes actions on your computer.

## What he can do
- Chat about anything and remember the conversation
- Open websites ("Alfred, open YouTube")
- Search Google or YouTube ("Alfred, search for lasagna recipes on YouTube")
- Open any installed app, including Microsoft Store apps ("Alfred, open Spotify")
- Save, read and delete notes ("Alfred, take a note that I have a test on Friday")
- Tell the date and time
- Text mode, if you don't have a microphone

## Quick start (Windows)
1. Install **Python 3.13** (the microphone library does not support 3.14 on Windows yet). With the Python install manager, run `py install 3.13` in cmd.
2. Download this project (green **Code** button > **Download ZIP**) and extract it.
3. Create an API key at https://console.anthropic.com (**API Keys**) and add credits under **Billing**.
4. Double-click **`install.bat`** and paste your key when asked.
5. Double-click **`run.bat`** and say *"Alfred, what time is it?"*

## Manual setup (Mac/Linux)
```bash
git clone https://github.com/ArthurMT120207/alfred.git
cd alfred
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then put your key in .env
python alfred.py          # voice mode
python alfred.py --text   # text mode
```
> **PyAudio error?** Mac: `brew install portaudio`. Linux: `sudo apt install portaudio19-dev python3-pyaudio`.

⚠️ Never upload your `.env` file to GitHub (the `.gitignore` already prevents this).

## Customization
In `.env` you can change the model, the wake word and how Alfred addresses you.
To add new actions, add an entry to `TOOLS` and handle it in `run_tool()` in `alfred.py`.

## Ideas for future versions
- Batcomputer-style graphical interface
- More realistic voice (ElevenLabs, OpenAI TTS)
- Music, volume and messaging control
- Calendar and email integration
