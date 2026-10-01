# ALFRED 🦇

Assistente pessoal por voz, que fala e entende **inglês**, movido pelo Claude (Anthropic).
Diga **"Alfred"** + seu pedido e ele responde falando e executa ações no seu computador.

## O que ele faz
> O Alfred escuta e responde em inglês, com voz britânica quando o seu sistema tiver uma. Exemplo: *"Alfred, open YouTube"*.

- Conversa sobre qualquer assunto e lembra do contexto da conversa
- Abre sites ("Alfred, open YouTube")
- Pesquisa no Google ou YouTube ("Alfred, search for lasagna recipes on YouTube")
- Abre programas ("Alfred, open the calculator")
- Salva, lê e apaga notas/lembretes ("Alfred, take a note that I have a test on Friday")
- Sabe a data e a hora
- Modo texto, se você não tiver microfone

## Passo a passo

### 1. Instale o Python
Baixe o Python 3.10+ em https://python.org (no Windows, marque **"Add Python to PATH"**).

### 2. Baixe o projeto
```bash
git clone https://github.com/ArthurMT120207/alfred.git
cd alfred
```

### 3. Crie um ambiente virtual e instale as dependências
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
```
> **Erro no PyAudio?**
> Windows: `pip install pipwin && pipwin install pyaudio`
> Mac: `brew install portaudio` e depois `pip install pyaudio`
> Linux: `sudo apt install portaudio19-dev python3-pyaudio`

### 4. Pegue sua chave da API
1. Acesse https://console.anthropic.com e crie uma conta
2. Vá em **API Keys** e crie uma chave
3. Adicione créditos em **Billing** (o uso é pago por consumo, normalmente centavos por conversa)

### 5. Configure
Copie `.env.example` para `.env` e cole sua chave:
```
ANTHROPIC_API_KEY=sk-ant-...
```
⚠️ Nunca suba o `.env` para o GitHub (o `.gitignore` já impede isso).

### 6. Rode
```bash
python alfred.py          # modo voz
python alfred.py --texto  # modo texto
```

## Personalização
No `.env` você pode mudar o modelo, a palavra de ativação e como o Alfred te chama.
Para adicionar novas ações, crie uma entrada em `FERRAMENTAS` e trate ela em `executar_ferramenta()` no `alfred.py`.

## Ideias para próximas versões
- Interface gráfica estilo Batcomputador
- Voz mais realista (ElevenLabs, OpenAI TTS)
- Controle de música, volume e mensagens
- Integração com agenda e e-mail
