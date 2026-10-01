"""
ALFRED - Assistente pessoal por voz usando Claude (Anthropic).

Modos:
    python alfred.py           -> modo voz (diga "Alfred" + seu pedido)
    python alfred.py --texto   -> modo texto (digita no terminal)
"""

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
# Configuração
# ----------------------------------------------------------------------------
MODELO = os.getenv("ALFRED_MODELO", "claude-sonnet-5-5")
PALAVRA_ATIVACAO = os.getenv("ALFRED_PALAVRA", "alfred").lower()
NOME_USUARIO = os.getenv("ALFRED_USUARIO", "sir")
ARQUIVO_NOTAS = Path(__file__).parent / "notas.json"
MAX_HISTORICO = 20  # mensagens mantidas na memória da conversa

SYSTEM_PROMPT = f"""You are ALFRED, an intelligent, polite and efficient personal assistant,
inspired by Batman's loyal butler, with a refined British manner.
You ALWAYS speak and answer in English, even if the user speaks another language.
Address the user as "{NOME_USUARIO}".
Your answers will be SPOKEN out loud, so:
- Be brief and direct (1 to 3 sentences, unless asked for detail).
- Do not use markdown, lists, emojis or symbols.
Use the available tools when the request involves actions on the computer,
the time, notes or web searches. Current date and time: {{agora}}."""

# ----------------------------------------------------------------------------
# Ferramentas (ações que o Alfred pode executar)
# ----------------------------------------------------------------------------
FERRAMENTAS = [
    {
        "name": "abrir_site",
        "description": "Abre um site no navegador padrão.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "Endereço do site, ex: youtube.com"}},
            "required": ["url"],
        },
    },
    {
        "name": "pesquisar_web",
        "description": "Pesquisa algo no Google ou no YouTube e abre o resultado no navegador.",
        "input_schema": {
            "type": "object",
            "properties": {
                "termo": {"type": "string"},
                "onde": {"type": "string", "enum": ["google", "youtube"]},
            },
            "required": ["termo"],
        },
    },
    {
        "name": "abrir_programa",
        "description": "Abre um programa instalado no computador (ex: calculadora, bloco de notas, spotify).",
        "input_schema": {
            "type": "object",
            "properties": {"nome": {"type": "string"}},
            "required": ["nome"],
        },
    },
    {
        "name": "salvar_nota",
        "description": "Salva uma nota ou lembrete para o usuário.",
        "input_schema": {
            "type": "object",
            "properties": {"texto": {"type": "string"}},
            "required": ["texto"],
        },
    },
    {
        "name": "ler_notas",
        "description": "Lê todas as notas e lembretes salvos.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "apagar_notas",
        "description": "Apaga todas as notas salvas. Só use se o usuário pedir claramente.",
        "input_schema": {"type": "object", "properties": {}},
    },
]

# Atalhos de programas comuns por sistema operacional
PROGRAMAS = {
    "Windows": {
        "calculadora": "calc",
        "bloco de notas": "notepad",
        "explorador": "explorer",
        "paint": "mspaint",
        "spotify": "spotify",
        "vscode": "code",
        "chrome": "chrome",
    },
    "Darwin": {
        "calculadora": "Calculator",
        "bloco de notas": "TextEdit",
        "explorador": "Finder",
        "spotify": "Spotify",
        "vscode": "Visual Studio Code",
        "chrome": "Google Chrome",
    },
    "Linux": {
        "calculadora": "gnome-calculator",
        "bloco de notas": "gedit",
        "explorador": "nautilus",
        "spotify": "spotify",
        "vscode": "code",
        "chrome": "google-chrome",
    },
}


def _carregar_notas() -> list:
    try:
        return json.loads(ARQUIVO_NOTAS.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def executar_ferramenta(nome: str, args: dict) -> str:
    """Executa uma ferramenta e devolve o resultado em texto para o Claude."""
    try:
        if nome == "abrir_site":
            url = args["url"]
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            webbrowser.open(url)
            return f"Site {url} aberto."

        if nome == "pesquisar_web":
            termo = quote_plus(args["termo"])
            if args.get("onde") == "youtube":
                url = f"https://www.youtube.com/results?search_query={termo}"
            else:
                url = f"https://www.google.com/search?q={termo}"
            webbrowser.open(url)
            return f"Pesquisa aberta: {url}"

        if nome == "abrir_programa":
            sistema = platform.system()
            pedido = args["nome"].lower().strip()
            comando = PROGRAMAS.get(sistema, {}).get(pedido, pedido)
            if sistema == "Windows":
                os.startfile(comando) if os.path.exists(comando) else subprocess.Popen(
                    f'start "" "{comando}"', shell=True)
            elif sistema == "Darwin":
                subprocess.Popen(["open", "-a", comando])
            else:
                subprocess.Popen([comando])
            return f"Programa '{pedido}' aberto."

        if nome == "salvar_nota":
            notas = _carregar_notas()
            notas.append({"texto": args["texto"], "data": datetime.now().strftime("%d/%m/%Y %H:%M")})
            ARQUIVO_NOTAS.write_text(json.dumps(notas, ensure_ascii=False, indent=2), encoding="utf-8")
            return "Nota salva."

        if nome == "ler_notas":
            notas = _carregar_notas()
            if not notas:
                return "Nenhuma nota salva."
            return "\n".join(f"{n['data']}: {n['texto']}" for n in notas)

        if nome == "apagar_notas":
            ARQUIVO_NOTAS.write_text("[]", encoding="utf-8")
            return "Todas as notas foram apagadas."

        return f"Ferramenta desconhecida: {nome}"
    except Exception as e:  # noqa: BLE001
        return f"Erro ao executar {nome}: {e}"


# ----------------------------------------------------------------------------
# Cérebro (Claude)
# ----------------------------------------------------------------------------
class Cerebro:
    def __init__(self):
        if not os.getenv("ANTHROPIC_API_KEY"):
            sys.exit("ERRO: defina ANTHROPIC_API_KEY no arquivo .env (veja o README).")
        self.cliente = anthropic.Anthropic()
        self.historico: list = []

    def pensar(self, pedido: str) -> str:
        self.historico.append({"role": "user", "content": pedido})
        system = SYSTEM_PROMPT.replace("{agora}", datetime.now().strftime("%A, %d/%m/%Y %H:%M"))

        while True:
            resposta = self.cliente.messages.create(
                model=MODELO,
                max_tokens=1024,
                system=system,
                tools=FERRAMENTAS,
                messages=self.historico,
            )
            self.historico.append({"role": "assistant", "content": resposta.content})

            if resposta.stop_reason != "tool_use":
                break

            resultados = []
            for bloco in resposta.content:
                if bloco.type == "tool_use":
                    print(f"  [ação] {bloco.name} {bloco.input}")
                    resultados.append({
                        "type": "tool_result",
                        "tool_use_id": bloco.id,
                        "content": executar_ferramenta(bloco.name, bloco.input),
                    })
            self.historico.append({"role": "user", "content": resultados})

        self._podar_historico()
        return "".join(b.text for b in resposta.content if b.type == "text").strip()

    def _podar_historico(self):
        # Mantém a conversa curta, sempre começando numa mensagem de texto do usuário
        while len(self.historico) > MAX_HISTORICO:
            self.historico.pop(0)
            while self.historico and not (
                self.historico[0]["role"] == "user" and isinstance(self.historico[0]["content"], str)
            ):
                self.historico.pop(0)


# ----------------------------------------------------------------------------
# Voz (fala e escuta)
# ----------------------------------------------------------------------------
class Voz:
    def __init__(self):
        import pyttsx3
        self.motor = pyttsx3.init()
        self.motor.setProperty("rate", 185)
        for v in self.motor.getProperty("voices"):
            info = f"{v.id} {v.name} {getattr(v, 'languages', '')}".lower()
            # Prefere uma voz em inglês (britânica, se houver)
            if "en_gb" in info or "en-gb" in info or "united kingdom" in info or "george" in info or "hazel" in info:
                self.motor.setProperty("voice", v.id)
                break
            if "english" in info or "en_us" in info or "en-us" in info or "david" in info or "zira" in info:
                self.motor.setProperty("voice", v.id)
                break

    def falar(self, texto: str):
        print(f"ALFRED: {texto}")
        self.motor.say(texto)
        self.motor.runAndWait()


class Ouvido:
    def __init__(self):
        import speech_recognition as sr
        self.sr = sr
        self.reconhecedor = sr.Recognizer()
        self.reconhecedor.pause_threshold = 0.8
        self.microfone = sr.Microphone()
        with self.microfone as fonte:
            print("Calibrando o microfone (fique em silêncio)...")
            self.reconhecedor.adjust_for_ambient_noise(fonte, duration=1.5)

    def ouvir(self) -> str:
        with self.microfone as fonte:
            try:
                audio = self.reconhecedor.listen(fonte, timeout=None, phrase_time_limit=12)
            except self.sr.WaitTimeoutError:
                return ""
        try:
            return self.reconhecedor.recognize_google(audio, language="en-US")
        except (self.sr.UnknownValueError, self.sr.RequestError):
            return ""


# ----------------------------------------------------------------------------
# Loops principais
# ----------------------------------------------------------------------------
SAIR = {"exit", "quit", "goodbye", "shutdown", "sair"}


def modo_texto(cerebro: Cerebro):
    print(f"ALFRED (modo texto). Digite '{'/'.join(sorted(SAIR))}' para encerrar.\n")
    while True:
        try:
            pedido = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not pedido:
            continue
        if pedido.lower() in SAIR:
            print(f"ALFRED: Goodbye, {NOME_USUARIO}.")
            break
        print(f"ALFRED: {cerebro.pensar(pedido)}\n")


def modo_voz(cerebro: Cerebro):
    voz = Voz()
    ouvido = Ouvido()
    voz.falar(f"Good evening, {NOME_USUARIO}. At your service.")
    print(f"Diga '{PALAVRA_ATIVACAO}' seguido do seu pedido. Ctrl+C para sair.\n")

    while True:
        frase = ouvido.ouvir().lower()
        if not frase:
            continue
        print(f"(ouvi: {frase})")
        if PALAVRA_ATIVACAO not in frase:
            continue

        pedido = frase.split(PALAVRA_ATIVACAO, 1)[1].strip(" ,.")
        if not pedido:
            voz.falar("Yes, sir?")
            pedido = ouvido.ouvir()
            if not pedido:
                continue
        if any(p in pedido.lower().split() for p in SAIR):
            voz.falar(f"Shutting down. Goodbye, {NOME_USUARIO}.")
            break
        try:
            voz.falar(cerebro.pensar(pedido))
        except anthropic.APIError as e:
            voz.falar("I am afraid I could not reach my servers, sir.")
            print(f"  [erro] {e}")


def main():
    cerebro = Cerebro()
    if "--texto" in sys.argv:
        modo_texto(cerebro)
        return
    try:
        modo_voz(cerebro)
    except KeyboardInterrupt:
        print("\nALFRED desligado.")
    except Exception as e:  # noqa: BLE001
        print(f"Não consegui iniciar o modo voz ({e}). Entrando no modo texto.\n")
        modo_texto(cerebro)


if __name__ == "__main__":
    main()
