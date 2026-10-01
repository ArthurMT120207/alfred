"""
ALFRED - Voice-powered personal assistant using Claude (Anthropic).

Modes:
    python alfred.py          -> voice mode (say "Alfred" + your request)
    python alfred.py --text   -> text mode (type in the terminal)
"""

import difflib
import json
import os
import platform
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
import anthropic

load_dotenv()

# ----------------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------------
MODEL = os.getenv("ALFRED_MODEL", "claude-sonnet-5-5")
WAKE_WORD = os.getenv("ALFRED_WAKE_WORD", "alfred").lower()
# Common ways speech recognition "hears" the word Alfred
WAKE_WORD_VARIANTS = [WAKE_WORD, "alfredo", "alfred's", "all fred", "al fred",
                      "alford", "alfret", "elfred", "hey alfred"]
USER_TITLE = os.getenv("ALFRED_USER_TITLE", "sir")
NOTES_FILE = Path(__file__).parent / "notes.json"
MAX_HISTORY = 20  # messages kept in conversation memory

SYSTEM_PROMPT = f"""You are ALFRED, an intelligent, polite and efficient personal assistant,
inspired by Batman's loyal butler, with a refined British manner.
You ALWAYS speak and answer in English.
Address the user as "{USER_TITLE}".
Your answers will be SPOKEN out loud, so:
- Be brief and direct (1 to 3 sentences, unless asked for detail).
- Do not use markdown, lists, emojis or symbols.
Use the available tools when the request involves actions on the computer,
the time, notes or web searches. Current date and time: {{now}}."""

# ----------------------------------------------------------------------------
# Tools (actions Alfred can perform)
# ----------------------------------------------------------------------------
TOOLS = [
    {
        "name": "open_website",
        "description": "Opens a website in the default browser.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "Website address, e.g. youtube.com"}},
            "required": ["url"],
        },
    },
    {
        "name": "web_search",
        "description": "Searches Google or YouTube and opens the results in the browser.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "where": {"type": "string", "enum": ["google", "youtube"]},
            },
            "required": ["query"],
        },
    },
    {
        "name": "open_app",
        "description": ("Opens any app installed on the computer (e.g. spotify, discord, calculator, "
                        "notepad, chrome, whatsapp, steam, settings). Pass the app name as the user said it. "
                        "If it fails, tell the user the app was not found."),
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "save_note",
        "description": "Saves a note or reminder for the user.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "read_notes",
        "description": "Reads all saved notes and reminders.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "delete_notes",
        "description": "Deletes all saved notes. Only use if the user clearly asks for it.",
        "input_schema": {"type": "object", "properties": {}},
    },
]

# Shortcuts for common apps, per operating system
APP_SHORTCUTS = {
    "Windows": {
        "calculator": "calc",
        "notepad": "notepad",
        "file explorer": "explorer",
        "explorer": "explorer",
        "files": "explorer",
        "paint": "mspaint",
        "settings": "ms-settings:",
        "task manager": "taskmgr",
        "command prompt": "cmd",
        "terminal": "wt",
    },
    "Darwin": {
        "calculator": "Calculator",
        "notepad": "TextEdit",
        "file explorer": "Finder",
        "files": "Finder",
        "spotify": "Spotify",
        "vscode": "Visual Studio Code",
        "chrome": "Google Chrome",
    },
    "Linux": {
        "calculator": "gnome-calculator",
        "notepad": "gedit",
        "file explorer": "nautilus",
        "files": "nautilus",
        "spotify": "spotify",
        "vscode": "code",
        "chrome": "google-chrome",
    },
}

# Nicknames -> real app names (Windows search)
APP_NICKNAMES = {"vs code": "visual studio code", "vscode": "visual studio code"}


# ----------------------------------------------------------------------------
# Open any installed app (Windows)
# ----------------------------------------------------------------------------
_APPS_CACHE = None


def _windows_apps() -> dict:
    """Lists Start Menu apps (including Microsoft Store apps). {name: AppID}"""
    global _APPS_CACHE
    if _APPS_CACHE is None:
        _APPS_CACHE = {}
        try:
            output = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-StartApps | ConvertTo-Json -Compress"],
                capture_output=True, text=True, timeout=20,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).stdout
            data = json.loads(output) if output.strip() else []
            if isinstance(data, dict):
                data = [data]
            for app in data:
                _APPS_CACHE[app["Name"].lower()] = app["AppID"]
        except Exception as e:  # noqa: BLE001
            print(f"  [warning] could not list installed apps: {e}")
    return _APPS_CACHE


def _find_app(request: str, names: list) -> str | None:
    """Finds the app name that best matches the request."""
    request = request.lower().strip()
    for test in (
        lambda n: n == request,
        lambda n: n.startswith(request),
        lambda n: request in n,
        lambda n: all(word in n for word in request.split()),
    ):
        matches = sorted((n for n in names if test(n)), key=len)
        if matches:
            return matches[0]
    close = difflib.get_close_matches(request, names, n=1, cutoff=0.6)
    return close[0] if close else None


def open_windows_app(request: str) -> str:
    request = request.lower().strip()
    shortcut = APP_SHORTCUTS["Windows"].get(request)
    if shortcut:
        os.startfile(shortcut)
        return f"Opened {request}."

    apps = _windows_apps()
    name = _find_app(APP_NICKNAMES.get(request, request), list(apps))
    if name:
        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{apps[name]}"])
        return f"Opened {name}."

    return f"App '{request}' not found on this computer."


# ----------------------------------------------------------------------------
# Notes
# ----------------------------------------------------------------------------
def _load_notes() -> list:
    try:
        return json.loads(NOTES_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def run_tool(name: str, args: dict) -> str:
    """Runs a tool and returns the result as text for Claude."""
    try:
        if name == "open_website":
            url = args["url"]
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            webbrowser.open(url)
            return f"Opened {url}."

        if name == "web_search":
            query = quote_plus(args["query"])
            if args.get("where") == "youtube":
                url = f"https://www.youtube.com/results?search_query={query}"
            else:
                url = f"https://www.google.com/search?q={query}"
            webbrowser.open(url)
            return f"Search opened: {url}"

        if name == "open_app":
            system = platform.system()
            request = args["name"].lower().strip()
            if system == "Windows":
                return open_windows_app(request)
            command = APP_SHORTCUTS.get(system, {}).get(request, request)
            if system == "Darwin":
                subprocess.Popen(["open", "-a", command])
            else:
                subprocess.Popen([command])
            return f"Opened {request}."

        if name == "save_note":
            notes = _load_notes()
            notes.append({"text": args["text"], "date": datetime.now().strftime("%Y-%m-%d %H:%M")})
            NOTES_FILE.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
            return "Note saved."

        if name == "read_notes":
            notes = _load_notes()
            if not notes:
                return "No notes saved."
            return "\n".join(f"{n['date']}: {n['text']}" for n in notes)

        if name == "delete_notes":
            NOTES_FILE.write_text("[]", encoding="utf-8")
            return "All notes deleted."

        return f"Unknown tool: {name}"
    except Exception as e:  # noqa: BLE001
        return f"Error running {name}: {e}"


# ----------------------------------------------------------------------------
# Brain (Claude)
# ----------------------------------------------------------------------------
class Brain:
    def __init__(self):
        if not os.getenv("ANTHROPIC_API_KEY"):
            sys.exit("ERROR: set ANTHROPIC_API_KEY in the .env file (see README).")
        self.client = anthropic.Anthropic()
        self.history: list = []

    def think(self, request: str) -> str:
        self.history.append({"role": "user", "content": request})
        system = SYSTEM_PROMPT.replace("{now}", datetime.now().strftime("%A, %B %d, %Y %I:%M %p"))

        while True:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=system,
                tools=TOOLS,
                messages=self.history,
            )
            self.history.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                break

            results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  [action] {block.name} {block.input}")
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": run_tool(block.name, block.input),
                    })
            self.history.append({"role": "user", "content": results})

        self._trim_history()
        return "".join(b.text for b in response.content if b.type == "text").strip()

    def _trim_history(self):
        # Keeps the conversation short, always starting on a user text message
        while len(self.history) > MAX_HISTORY:
            self.history.pop(0)
            while self.history and not (
                self.history[0]["role"] == "user" and isinstance(self.history[0]["content"], str)
            ):
                self.history.pop(0)


# ----------------------------------------------------------------------------
# Voice (speaking and listening)
# ----------------------------------------------------------------------------
class Voice:
    def __init__(self):
        import pyttsx3
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", 185)
        voices = self.engine.getProperty("voices")

        def info(v):
            return f"{v.id} {v.name} {getattr(v, 'languages', '')}".lower()

        british = [v for v in voices if any(k in info(v) for k in ("en_gb", "en-gb", "united kingdom", "george", "hazel"))]
        english = [v for v in voices if any(k in info(v) for k in ("english", "en_us", "en-us", "david", "zira"))]
        chosen = (british or english or [None])[0]
        if chosen:
            self.engine.setProperty("voice", chosen.id)

    def say(self, text: str):
        print(f"ALFRED: {text}")
        self.engine.say(text)
        self.engine.runAndWait()


class Ears:
    def __init__(self):
        import speech_recognition as sr
        self.sr = sr
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 0.8
        self.microphone = sr.Microphone()
        with self.microphone as source:
            print("Calibrating microphone (please stay quiet)...")
            self.recognizer.adjust_for_ambient_noise(source, duration=1.5)

    def listen(self) -> str:
        with self.microphone as source:
            try:
                audio = self.recognizer.listen(source, timeout=None, phrase_time_limit=12)
            except self.sr.WaitTimeoutError:
                return ""
        try:
            return self.recognizer.recognize_google(audio, language="en-US")
        except (self.sr.UnknownValueError, self.sr.RequestError):
            return ""


# ----------------------------------------------------------------------------
# Main loops
# ----------------------------------------------------------------------------
EXIT_WORDS = {"exit", "quit", "goodbye", "shutdown"}


def text_mode(brain: Brain):
    print(f"ALFRED (text mode). Type '{'/'.join(sorted(EXIT_WORDS))}' to quit.\n")
    while True:
        try:
            request = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not request:
            continue
        if request.lower() in EXIT_WORDS:
            print(f"ALFRED: Goodbye, {USER_TITLE}.")
            break
        print(f"ALFRED: {brain.think(request)}\n")


def voice_mode(brain: Brain):
    voice = Voice()
    ears = Ears()
    voice.say(f"Good evening, {USER_TITLE}. At your service.")
    print(f"Say '{WAKE_WORD.title()}' followed by your request. Press Ctrl+C to quit.\n")

    while True:
        phrase = ears.listen().lower()
        if not phrase:
            continue
        print(f"(heard: {phrase})")
        trigger = next((v for v in WAKE_WORD_VARIANTS if v in phrase), None)
        if not trigger:
            print(f"  (tip: start your sentence with '{WAKE_WORD.title()}')")
            continue

        request = phrase.split(trigger, 1)[1].strip(" ,.")
        if not request:
            voice.say(f"Yes, {USER_TITLE}?")
            request = ears.listen()
            if not request:
                continue
        if any(word in request.lower().split() for word in EXIT_WORDS):
            voice.say(f"Shutting down. Goodbye, {USER_TITLE}.")
            break
        try:
            voice.say(brain.think(request))
        except anthropic.APIError as e:
            voice.say(f"I am afraid I could not reach my servers, {USER_TITLE}.")
            print(f"  [error] {e}")


def main():
    brain = Brain()
    if "--text" in sys.argv:
        text_mode(brain)
        return
    try:
        voice_mode(brain)
    except KeyboardInterrupt:
        print("\nALFRED shut down.")
    except Exception as e:  # noqa: BLE001
        print(f"Could not start voice mode ({e}). Switching to text mode.\n")
        text_mode(brain)


if __name__ == "__main__":
    main()
