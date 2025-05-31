import threading
import azure.cognitiveservices.speech as speechsdk
import re
import time
import asyncio
import vlc
import tempfile
import sqlite3
import hashlib
import config
import os

from pathlib import Path
from openai import OpenAI
from openai import AsyncOpenAI
from shutil import copy
from LanguageValidator import language_validator
from Observer import Observer

#OPEN AI
asyncOpenAi = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
clientOpenAI = OpenAI(api_key=config.OPENAI_API_KEY)

#AZURE
speech_key = config.AZURE_SPEECH_KEY
service_region = "eastus"

speech_config = speechsdk.SpeechConfig(
    subscription=speech_key, region=service_region, speech_recognition_language='pt-BR')
speech_config.speech_synthesis_voice_name = "pt-BR-ThalitaNeural"
speech_config.speech_synthesis_language = 'pt-BR'

speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)

#DATABASE
connection = sqlite3.connect('audios.db')
cursor = connection.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS audios (
                    id TEXT PRIMARY KEY
                )''')

class CustomAudioPlayer:
    def __init__(self, vlc):
        self.player = vlc

    async def play(self, response, sha256):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            async for chunk in response.iter_bytes():
                tmp.write(chunk)
            tmp_path = tmp.name

        media = vlc.Media(tmp_path)
        self.player.set_media(media)
        self.player.play()
        copy(tmp_path, Path(__file__).parent /f"audios/{sha256}.wav")


class TextReader(Observer):
    reading = None
    text_to_read = None
    text_to_read_array = None
    speech_history = []
    count_chars_read = 0
    count_cloud_speech_call = 0
    time = None
    player = vlc.MediaPlayer()
    customPlayer = CustomAudioPlayer(player)

    def speech(self, text):
        self.time = time.time()

        if len(self.speech_history) > 20:
            self.speech_history.clear()

        filtered_array = filter(None, text.split('\n'))
        self.text_to_read_array = list(filtered_array)

        text_without_commands = self.remove_board_commands()
        self.text_to_read = ' '.join(text_without_commands)
        self.clean_up_text()
        
        if self.text_to_read in self.speech_history:
            print("Pulando leitura - Se encontra no histórico")
            return
        
        predictions, is_valid = language_validator.validate(self.text_to_read)
        if not is_valid:
            print(f"Pulando leitura - O texto não é válido - Texto: {self.text_to_read}")
            return
        
        if self.text_to_read:
            print(f"Speech text: \n\"{self.text_to_read}\"\n")

            sha256_hash = hashlib.sha256(self.text_to_read.encode("utf-8")).hexdigest()
            cursor.execute(f"SELECT * FROM audios WHERE id = '{sha256_hash}' limit 1")
            rows = cursor.fetchall()

            if len(rows) == 1:
                hash = rows[0][0]
                print(f"Hash - {hash}")
                audio_path = f"audios/{rows[0][0]}.wav"
                if os.path.exists(audio_path):
                    print(f"Arquivo de áudio encontrado: {audio_path}")
                    media = vlc.Media(audio_path)
                    self.player.set_media(media)
                    self.player.play()
                    self.speech_history.append(self.text_to_read)
                    return
                else:
                    cursor.execute(f"DELETE FROM audios where id = '{hash}'")
                    print(f"Arquivo de áudio não encontrado: {audio_path} - Excluído da base de dados")
            
            cursor.execute("INSERT INTO audios (id) VALUES (?)", (sha256_hash,))
            connection.commit()    

            t1 = threading.Thread(target=self.run_chat_gpt_async_in_thread, daemon=True)
            t1.start()

            self.count_cloud_speech_call +=1 
            self.count_chars_read += len(self.text_to_read)

            print("\n")
            print(f"Found languages: {predictions}")
            print(f"Calls to speech: {self.count_cloud_speech_call}")
            print(f"Chars read: {self.count_chars_read}")

    def run_chat_gpt_async_in_thread(self):
        asyncio.run(TextReader.read_text_chat_gpt_async(self))

    async def read_text_chat_gpt_async(self):
        text_to_read_now = self.text_to_read
    
        async with asyncOpenAi.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice="coral",
            input=self.text_to_read,
            instructions="Leia como um narrador de \"O Senhor dos Anéis\", com emoção. Leia em português do Brasil",
            response_format="wav",
        ) as response:
            print(f"Speech process time: {time.time() - self.time}")
            self.reading = True
            await self.customPlayer.play(response, hashlib.sha256(self.text_to_read.encode("utf-8")).hexdigest())

        if self.text_to_read == text_to_read_now:
            self.speech_history.append(self.text_to_read)

        self.reading = False

    def read_text_chat_gpt(self):
        text_to_read_now = self.text_to_read
       
        speech_file_path = Path(__file__).parent / "speech.mp3"

        with clientOpenAI.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice="coral",
            input=text_to_read_now,
            instructions="Leia como um narrador de \"O Senhor dos Anéis\", com emoção. Leia em português do Brasil",
        ) as response:
            response.stream_to_file(speech_file_path)

        self.reading = True    

        media = vlc.Media(speech_file_path)
        self.player.set_media(media)
        self.player.play()

        print(f"Speech process time: {time.time() - self.time}")
        if self.text_to_read == text_to_read_now:
            self.speech_history.append(self.text_to_read)


    def read_text_azure(self):
        text_to_read_now = self.text_to_read
        speech_synthesizer.stop_speaking_async()
        
        self.reading = True
        speech_synthesizer.speak_text_async(self.text_to_read).get()

        if self.text_to_read == text_to_read_now:
            self.speech_history.append(self.text_to_read)

        self.reading = False

    #image changed
    def update(self, value):
        if self.player.is_playing() and value is False:
            print(f"Force stop audio")
            self.player.stop()
            self.reading = False
            self.text_to_read = None

        if self.reading and value is False:
            print(f"Force stop audio")
            speech_synthesizer.stop_speaking_async()
            self.reading = False
            self.text_to_read = None

    def remove_board_commands(self):
        result_parts = []
        for txt in self.text_to_read_array:

            if not txt.strip():
                break

            if re.search(r"Mova \d{1}", txt, re.IGNORECASE):
                break
            if re.search(r"Mover \d{1}", txt, re.IGNORECASE):
                break
            if re.search(r"Sofra \d{1}", txt, re.IGNORECASE):
                break
            if re.search(r"sofr[ea] \d{1}", txt, re.IGNORECASE):
                break
            if re.search(r"\d{3}[ab]", txt, re.IGNORECASE):
                break
            if re.search(r"^Voc[eê] ou um her[oó]i próximo", txt, re.IGNORECASE):
                break
            if re.search(r"coloque fichas de", txt, re.IGNORECASE):
                break
            if re.search(r"sua jornada continua..", txt, re.IGNORECASE):
                break
            if re.search(r"Esta [eé] uma resist[eê]ncia final de", txt, re.IGNORECASE):
                break
            if re.search(r"Um her[oó]i com uma ficha de", txt, re.IGNORECASE):
                break

            if re.search(r"^etapa da escurid", txt, re.IGNORECASE):
                break
            if re.search(r"^As sombras se intensificam", txt, re.IGNORECASE):
                break
            if re.search(r"^Aumente a amea", txt, re.IGNORECASE):
                break
            if re.search(r"^O inimigo pode atacar", txt, re.IGNORECASE):
                break
            if re.search(r"Encerrar a fase de", txt, re.IGNORECASE):
                break
            if re.search(r"^explorar?", txt, re.IGNORECASE):
                break
            if re.search(r"^Muro.", txt, re.IGNORECASE):
                break
            if re.search(r"^Fogueira.", txt, re.IGNORECASE):
                break
            if re.search(r"^Fogueira", txt):
                break
            if re.search(r"^Rocha.", txt, re.IGNORECASE):
                break
            if re.search(r"^Arbusto.", txt, re.IGNORECASE):
                break
            if re.search(r"^Teste ", txt, re.IGNORECASE):
                break
            if re.search(r"^Descarte ", txt, re.IGNORECASE):
                break
            if re.search(r"^Aumente o ", txt, re.IGNORECASE):
                break
            if re.search(r"^Ganhe ", txt, re.IGNORECASE):
                break
            if re.search(r"^Fique ", txt, re.IGNORECASE):
                break
            if re.search(r"^Objetivo final", txt, re.IGNORECASE):
                break
            if re.search(r"^Voc[eê] pode descartar ", txt, re.IGNORECASE):
                break
            if re.search(r"^Coloque um", txt, re.IGNORECASE):
                break
            if re.search(r"^Coloque ", txt, re.IGNORECASE):
                break
            if re.search(r"Cada her[oó]i testa", txt, re.IGNORECASE):
                break
            if re.search(r"Cada her[oó]i examina", txt, re.IGNORECASE):
                break
            if re.search(r"Cada her[oó]i sofre", txt, re.IGNORECASE):
                break
            if re.search(r"Cada her[oó]i ganha", txt, re.IGNORECASE):
                break
            if re.search(r"^O her[oó]i .*? testa", txt, re.IGNORECASE):
                break
            if re.search(r"Qual her[oó]i ganhou este t[ií]tulo", txt, re.IGNORECASE):
                break
            if re.search(r"Receba o t[ií]tulo", txt, re.IGNORECASE):
                break
            if re.search(r"Cada her[oó]i restaura seu baralho", txt, re.IGNORECASE):
                break
            if re.search(r"^Objetivo atualizado", txt, re.IGNORECASE):
                break
            if re.search(r"^Sem efeito.", txt, re.IGNORECASE):
                break
            if re.search(r"^Remova ", txt, re.IGNORECASE):
                break
            if re.search(r"^Negado por ", txt, re.IGNORECASE):
                break
            if re.search(r"^Reduza a amec", txt, re.IGNORECASE):
                break
            if re.search(r"^Realizar uma resist", txt, re.IGNORECASE):
                break

            result_parts.append(txt.strip())

        return result_parts

    def clean_up_text(self):
        self.text_to_read = self.text_to_read.replace(';', '')
        self.text_to_read = self.text_to_read.replace('\'', '')
        self.text_to_read = self.text_to_read.replace('\"', '')
        self.text_to_read = self.text_to_read.replace('  ', ' ')
        self.text_to_read = self.text_to_read.replace('—', '. ')
        self.text_to_read = self.text_to_read.strip()
        #self.text_to_read = self.text_to_read.replace('Orc', 'Órque')
        #self.text_to_read = self.text_to_read.replace('orc', 'órque')
        #self.text_to_read = self.text_to_read.replace('Goblin', 'Góblin')
        #self.text_to_read = self.text_to_read.replace('goblin', 'góblin')
        self.text_to_read = self.text_to_read.replace('Guardiá', 'Guardiã')
        self.text_to_read = self.text_to_read.replace('guardiá', 'guardiã')
        self.text_to_read = self.text_to_read.replace('Guardiáo', 'Guardião')
        self.text_to_read = self.text_to_read.replace('guardião', 'guardião')
        self.text_to_read = self.text_to_read.replace('Legolas', 'Légolas')

        self.text_to_read = self.text_to_read.strip()


text_reader = TextReader()


