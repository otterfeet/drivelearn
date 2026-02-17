import json
import os
import time
import random
import threading
import wave
import struct
import math
from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.core.window import Window
from kivy.core.audio import SoundLoader
from kivy.clock import Clock, mainthread
from kivy.utils import platform

# ================= CONFIGURATION =================
EXTERNAL_FOLDER_NAME = "DriveLearn"
AUDIO_SUBFOLDER = "audio_files"
INTERVALS = [0, 1, 4, 36500] 
SESSION_LIMIT = 20
NEW_CARDS_PER_LAUNCH = 50
# =================================================

class DriveLearnApp(App):
    def build(self):
        self.state = "IDLE" 
        self.queue = []
        self.history = []
        self.current_card = None
        self.sound = None
        self.bg_noise = None 
        self.db = {}

        # --- UI LAYOUT ---
        self.layout = BoxLayout(orientation='vertical', padding=20, spacing=20)
        
        self.label = Label(
            text="Initializing...", 
            font_size='32sp', 
            halign="center", 
            valign="middle", 
            markup=True,
            size_hint=(1, 0.4)
        )
        self.label.bind(size=self.label.setter('text_size'))
        self.layout.add_widget(self.label)
        
        self.btn_next = Button(
            text="START / NEXT",
            font_size='24sp',
            background_color=(0, 0.8, 0, 1), 
            size_hint=(1, 0.4)
        )
        self.btn_next.bind(on_press=self.on_screen_button)
        self.layout.add_widget(self.btn_next)

        self.debug_label = Label(
            text="Waiting for input...", 
            font_size='14sp', 
            size_hint=(1, 0.1),
            color=(0.5, 0.5, 0.5, 1)
        )
        self.layout.add_widget(self.debug_label)

        Window.bind(on_key_down=self._on_keyboard_down)

        if platform == 'android':
            from android.permissions import request_permissions, Permission
            def callback(permissions, results):
                if all(results):
                    self.setup_storage_and_noise()
                else:
                    self.label.text = "Permission Denied!"

            request_permissions(
                [Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE], 
                callback
            )
            self.app_dir = os.path.join("/storage/emulated/0", EXTERNAL_FOLDER_NAME)
        else:
            self.app_dir = os.path.dirname(os.path.abspath(__file__))
            self.setup_storage_and_noise()

        return self.layout

    def setup_storage_and_noise(self):
        self.audio_dir = os.path.join(self.app_dir, AUDIO_SUBFOLDER)
        self.db_path = os.path.join(self.app_dir, 'progress.json')
        
        # 1. Start Noise Generator
        threading.Thread(target=self.generate_and_play_noise).start()
        
        # 2. Start Scanning Files
        self.start_background_load()

    def generate_and_play_noise(self):
        """ Generates a 20Hz Sine Wave (Inaudible but high energy) """
        noise_path = os.path.join(self.app_dir, "keepalive.wav")
        
        # Always regenerate to ensure we use the new louder version
        try:
            with wave.open(noise_path, 'w') as f:
                f.setnchannels(1) 
                f.setsampwidth(2) 
                f.setframerate(44100)
                
                # CONFIGURATION:
                duration = 10  # seconds
                frequency = 20 # Hz (Low rumble, invisible to ear)
                volume = 1500  # Amplitude (Much louder than before)
                
                data = bytearray()
                for i in range(44100 * duration):
                    # Sine wave formula
                    value = int(volume * math.sin(2 * math.pi * frequency * i / 44100))
                    data.extend(struct.pack('<h', value))
                    
                f.writeframes(data)
        except Exception as e:
            print(f"Noise gen failed: {e}")

        # Play loop on main thread
        Clock.schedule_once(lambda dt: self.start_noise_loop(noise_path), 1)

    @mainthread
    def start_noise_loop(self, filepath):
        if os.path.exists(filepath):
            self.bg_noise = SoundLoader.load(filepath)
            if self.bg_noise:
                self.bg_noise.loop = True
                self.bg_noise.volume = 0.5 # 50% volume of the 20Hz tone
                self.bg_noise.play()
                self.debug_label.text += " | DAC Awake (20Hz)"

    def start_background_load(self):
        self.label.text = "Scanning Files..."
        threading.Thread(target=self.load_data).start()

    def load_data(self):
        try:
            if os.path.exists(self.db_path):
                try:
                    with open(self.db_path, 'r') as f:
                        self.db = json.load(f)
                except: self.db = {}
            else: self.db = {}

            if os.path.exists(self.audio_dir):
                all_files = os.listdir(self.audio_dir)
                a_files = sorted([f for f in all_files if "_A_" in f and f.endswith(('.mp3', '.wav', '.ogg'))])
                
                new_added = 0
                for f_a in a_files:
                    if new_added >= NEW_CARDS_PER_LAUNCH: break
                    
                    word_id = f_a.split("_A_")[0]
                    if word_id not in self.db:
                        match_b = next((x for x in all_files if x.startswith(word_id) and "_B_" in x), None)
                        file_b = match_b if match_b else f_a
                        
                        self.db[word_id] = {
                            "box": 0, "due": 0,
                            "file_a": os.path.join(self.audio_dir, f_a),
                            "file_b": os.path.join(self.audio_dir, file_b)
                        }
                        new_added += 1
                
                if new_added > 0: self.save_db()
                Clock.schedule_once(self.build_session_queue, 0)
            else:
                self.show_error(f"Folder Missing:\n{self.audio_dir}")
        except Exception as e:
            self.show_error(f"Crash: {str(e)}")

    @mainthread
    def show_error(self, text):
        self.label.text = f"[color=ff0000]{text}[/color]"

    def save_db(self):
        try:
            with open(self.db_path, 'w') as f:
                json.dump(self.db, f)
        except: pass

    @mainthread
    def build_session_queue(self, dt=None):
        now = time.time()
        due = [k for k, v in self.db.items() if v.get('due', 0) <= now and 0 < v['box'] < 3]
        new_cards = [k for k, v in self.db.items() if v['box'] == 0]
        new_cards.sort() 
        
        slots = SESSION_LIMIT - len(due)
        self.queue = due + new_cards[:slots]
        random.shuffle(self.queue)
        
        if self.queue:
            self.label.text = f"Ready: {len(self.queue)} Cards\n\n[Press NEXT / UP]"
            self.state = "IDLE"
        else:
            self.label.text = "Session Complete!\nNo cards due."

    def play_audio(self, filepath):
        if self.sound:
            try: self.sound.stop()
            except: pass
        if os.path.exists(filepath):
            self.sound = SoundLoader.load(filepath)
            if self.sound: 
                self.sound.volume = 1.0 
                self.sound.play()

    def get_text(self, filepath):
        name = os.path.basename(filepath)
        if "_A_" in name: return name.split("_A_")[-1].replace(".mp3", "").replace("_", " ")
        if "_B_" in name: return name.split("_B_")[-1].replace(".mp3", "").replace("_", " ")
        return name

    # --- CORE ACTIONS ---

    def next_step(self):
        if not self.queue and not self.current_card:
            self.label.text = "Session Complete!"
            return

        if self.state == "IDLE" or self.state == "FINISHED_CARD":
            if not self.queue:
                self.label.text = "Session Complete!"
                return
            
            if self.current_card:
                self.history.append(self.current_card)
            
            self.current_card = self.queue.pop(0)
            self.state = "PLAYING_Q"
            
            data = self.db[self.current_card]
            self.label.text = f"[b]{self.get_text(data['file_a'])}[/b]\n(Box {data['box']})"
            self.label.color = (1, 1, 1, 1)
            self.play_audio(data['file_a'])
            
            self.btn_next.text = "SHOW ANSWER"
            self.btn_next.background_color = (0, 0.5, 1, 1)

        elif self.state == "PLAYING_Q":
            self.state = "PLAYING_A"
            data = self.db[self.current_card]
            self.label.text = f"[b]ANSWER[/b]\n{self.get_text(data['file_b'])}"
            self.label.color = (1, 1, 0, 1)
            self.play_audio(data['file_b'])
            
            self.btn_next.text = "NEXT (Fail)"
            self.btn_next.background_color = (1, 0, 0, 1)

        elif self.state == "PLAYING_A":
            self.grade_card(success=False)

    def rewind_action(self):
        if self.sound: self.sound.stop()

        if self.state == "PLAYING_A":
            self.state = "PLAYING_Q"
            data = self.db[self.current_card]
            self.label.text = f"[b]{self.get_text(data['file_a'])}[/b]\n(Box {data['box']})"
            self.label.color = (1, 1, 1, 1)
            self.play_audio(data['file_a'])
            self.btn_next.text = "SHOW ANSWER"
            self.btn_next.background_color = (0, 0.5, 1, 1)

        elif self.state == "PLAYING_Q" or self.state == "IDLE":
            if not self.history:
                self.label.text = "Cannot Rewind\n(Start of Session)"
                return

            if self.current_card:
                self.queue.insert(0, self.current_card)

            self.current_card = self.history.pop()
            
            self.state = "PLAYING_Q"
            data = self.db[self.current_card]
            self.label.text = f"<< REWINDING\n[b]{self.get_text(data['file_a'])}[/b]"
            self.label.color = (1, 1, 1, 1)
            self.play_audio(data['file_a'])
            
            self.btn_next.text = "SHOW ANSWER"
            self.btn_next.background_color = (0, 0.5, 1, 1)

    def mark_as_known(self):
        if self.current_card:
            self.label.text = "[b]MARKED KNOWN[/b]"
            self.label.color = (0, 1, 0, 1)
            self.grade_card(success=True)

    def grade_card(self, success):
        if not self.current_card: return
        data = self.db[self.current_card]
        
        if success:
            data['box'] += 1
            if data['box'] >= len(INTERVALS): data['box'] = len(INTERVALS) - 1
        else:
            data['box'] = 1 
        
        wait_days = INTERVALS[data['box']]
        if not success:
            data['due'] = time.time() + 300
            self.queue.append(self.current_card) 
        else:
            data['due'] = time.time() + (wait_days * 86400)

        threading.Thread(target=self.save_db).start()
        
        self.state = "FINISHED_CARD"
        self.next_step()

    def on_screen_button(self, instance):
        self.next_step()

    def _on_keyboard_down(self, window, keycode, scancode, text, modifiers):
        key_id = keycode[0] if isinstance(keycode, tuple) else keycode
        
        if key_id in [276, 25]: # Left / Vol Down
            self.mark_as_known()
            return True

        elif key_id in [273, 275, 24, 32, 13]: # Up / Right / Vol Up
            self.next_step()
            return True

        elif key_id == 274: # Down
            self.rewind_action()
            return True
            
        return False

if __name__ == '__main__':
    DriveLearnApp().run()
