import threading
import re
import time
import asyncio
import tempfile
import sqlite3
import hashlib
import config
import os
from shutil import copy

import vlc
import pyaudio
import wave

import azure.cognitiveservices.speech as speechsdk
from openai import OpenAI
from openai import AsyncOpenAI
from pathlib import Path

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

azure_speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)

#DATABASE
connection = sqlite3.connect('audios.db')
cursor = connection.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS audios (
                    id TEXT PRIMARY KEY
                )''')

#AUDIOS
class PyAudioStreamPlayer:
    stream = None
    is_playing = False
    player = None

    async def play(self, response, sha256):
        self.player = pyaudio.PyAudio()

        first_chunk_sent = False
        start = time.time()

        self.create_stream()
        self.is_playing = True

        pcm_audio = bytearray()

        async for chunk in response.iter_bytes(4096):
            if not self.is_playing:
                break

            pcm_audio.extend(chunk)
            self.stream.write(chunk)

            if not first_chunk_sent:
                elapsed_time = time.time() - start
                print(f"Time taken to send the first chunk: {elapsed_time:.4f}")
                first_chunk_sent = True

        if(config.SAVE_AUDIOS):
            self.save_audio(pcm_audio, sha256)

    def create_stream(self):
        self.stream = self.player.open(format=pyaudio.paInt16, 
                            channels=1,
                            rate=24000,
                            output=True,
                            frames_per_buffer=2048)
    def stop(self):
        self.is_playing = False
        time.sleep(1) # Prevent buffer underrun
        self.stream.stop_stream()   
        self.stream.close()
        self.player.terminate()
    
    def save_audio(self, pcm_bytes, sha256):
        file_name = f"audios/{sha256}.wav"
        output_path = Path(__file__).parent /file_name

        with wave.open(str(output_path), 'wb') as wav_file:
            wav_file.setnchannels(1)         # Mono
            wav_file.setsampwidth(2)         # 16 bits = 2 bytes
            wav_file.setframerate(24000)     # 24 kHz
            wav_file.writeframes(pcm_bytes)

        print(f"Saved audio - {file_name}")


class VlcWavAudioPlayer:
    def __init__(self, vlc):
        self.player = vlc

    async def play(self, response, sha256):
        start = time.time()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            async for chunk in response.iter_bytes():
                tmp.write(chunk)
            tmp_path = tmp.name

        media = vlc.Media(tmp_path)
        self.player.set_media(media)
        self.player.play()
        print("CustomAudioPlayer playing time {:.4f} ".format(time.time() - start))
        copy(tmp_path, Path(__file__).parent /f"audios/{sha256}.wav")

class TextReader(Observer):
    is_reading = None
    text_to_read = None
    text_to_read_array = None
    speech_history = []
    count_chars_read = 0
    count_cloud_speech_call = 0
    time = None
    player = vlc.MediaPlayer()
    vlcPlayer = VlcWavAudioPlayer(player)
    pyAudioStreamPlayer = PyAudioStreamPlayer()

    prompt = "Este texto faz parte de um jogo ambientado no universo de O Senhor dos Anéis. Analise o conteúdo dele e use o tom que melhor se adequar. Leia em português do Brasil."
    model = "gpt-4o-mini-tts"

    def speech(self, text):
        self.time = time.time()

        if len(self.speech_history) > config.SPEECH_HISTORY_SIZE_LIMIT:
            self.speech_history.clear()

        filtered_array = filter(None, text.split('\n'))
        self.text_to_read_array = list(filtered_array)

        text_without_commands = self.remove_game_commands()
        self.text_to_read = ' '.join(text_without_commands)
        self.clean_up_text()
        
        if self.text_to_read in self.speech_history:
            print(f"Pulando leitura - Se encontra no histórico - Configuração de {config.SPEECH_HISTORY_SIZE_LIMIT} espaços")
            return
        
        predictions, is_valid = language_validator.validate(self.text_to_read)
        if not is_valid:
            print(f"Found languages: {predictions}")
            print(f"Pulando leitura - O texto não é válido - Texto: {self.text_to_read}")
            return
        
        if self.text_to_read:
            print(f"Speech text: \n\"{self.text_to_read}\"\n")

            sha256_hash = hashlib.sha256(self.text_to_read.encode("utf-8")).hexdigest()
            cursor.execute(f"SELECT * FROM audios WHERE id = '{sha256_hash}' limit 1")
            rows = cursor.fetchall()

            if len(rows) == 1:
                hash = rows[0][0]
                print(f"Text hash - {hash}")
                audio_path = f"audios/{rows[0][0]}.wav"
                if os.path.exists(audio_path):
                    print(f"Found audio: {audio_path}")
                    if(config.PLAY_AUDIOS):
                        media = vlc.Media(audio_path)
                        self.player.set_media(media)
                        self.player.play()
                        self.speech_history.append(self.text_to_read)
                        return
                    else:
                        print("Configuration - Do not play audios")
                else:
                    cursor.execute(f"DELETE FROM audios where id = '{hash}'")
                    print(f"Arquivo de áudio não encontrado: {audio_path} - Excluído da base de dados")
            
            if(config.SAVE_AUDIOS_DB):
                cursor.execute("INSERT INTO audios (id) VALUES (?)", (sha256_hash,))
                connection.commit()   
            else:
                print("Configuration - Do not save audios in database")

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
        chat_gpt_time = time.time()
        async with asyncOpenAi.audio.speech.with_streaming_response.create(
            model=self.model,
            voice="coral",
            input=self.text_to_read,
            instructions=self.prompt,
            response_format="pcm",
        ) as response:
            print("Chat GPT process time: {:.4f}".format(time.time() - chat_gpt_time))
            print("Speech process time: {:.4f}".format(time.time() - self.time))
            self.is_reading = True
            await self.pyAudioStreamPlayer.play(response, hashlib.sha256(self.text_to_read.encode("utf-8")).hexdigest())

        if self.text_to_read == text_to_read_now:
            self.speech_history.append(self.text_to_read)

        self.is_reading = False

    def read_text_chat_gpt(self):
        text_to_read_now = self.text_to_read
       
        speech_file_path = Path(__file__).parent / "speech.mp3"

        with clientOpenAI.audio.speech.with_streaming_response.create(
            model=self.model,
            voice="coral",
            input=text_to_read_now,
            instructions=self.prompt,
        ) as response:
            response.stream_to_file(speech_file_path)

        self.is_reading = True    

        media = vlc.Media(speech_file_path)
        self.player.set_media(media)
        self.player.play()

        print("Speech process time: {:.4f}".format(time.time() - self.time))
        if self.text_to_read == text_to_read_now:
            self.speech_history.append(self.text_to_read)


    def read_text_azure(self):
        text_to_read_now = self.text_to_read
        azure_speech_synthesizer.stop_speaking_async()
        
        self.is_reading = True
        azure_speech_synthesizer.speak_text_async(self.text_to_read).get()

        if self.text_to_read == text_to_read_now:
            self.speech_history.append(self.text_to_read)

        self.is_reading = False

    #image changed
    def update(self, img_found):

        if self.pyAudioStreamPlayer.is_playing and img_found is False:
            print(f"Stopping audio - pyaudio")
            self.pyAudioStreamPlayer.stop()
            self.is_reading = False
            self.text_to_read = None

        if self.player.is_playing() and img_found is False:
            print(f"Stopping audio - vlc")
            self.player.stop()
            self.is_reading = False
            self.text_to_read = None

        if self.is_reading and img_found is False:
            print(f"Stopping audio - azure")
            azure_speech_synthesizer.stop_speaking_async()
            self.is_reading = False
            self.text_to_read = None

    def remove_game_commands(self):
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
            if re.search(r"^Vire \d{1}", txt, re.IGNORECASE):
                break
            if re.search(r"Fa[cç]a aparecer", txt, re.IGNORECASE):
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


