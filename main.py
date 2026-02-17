import json
import os
import time
import random
import threading  # <--- NEW: For background loading
from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.core.window import Window
from kivy.core.audio import SoundLoader
from kivy.clock import Clock, mainthread
from kivy.utils import platform

# ================= CONFIGURATION =================
EXTERNAL_FOLDER_NAME = "DriveLearn"
AUDIO_SUBFOLDER = "audio_files"
INTERVALS = [0, 1, 4, 36500] 
SESSION_LIMIT = 50
NEW_CARDS_PER_LAUNCH = 50  # <--- ONLY LOAD THIS MANY NEW WORDS AT A TIME
# =================================================

class DriveLearnApp(App):
    def build(self):
        self.state = "IDLE" 
        self.queue = []
        self.current_card = None
        self.sound = None
        self.db = {}

        # --- UI LAYOUT ---
        self.layout = BoxLayout(orientation='vertical', padding=20)
        
        self.label = Label(
            text="Initializing...", 
            font_size='32sp', 
            halign="center", 
            valign="middle", 
            markup=True
        )
        self.label.bind(size=self.label.setter('text_size'))
        self.layout.add_widget(self.label)
        
        self.debug_label = Label(
            text="Starting...", 
            font_size='14sp', 
            size_hint=(1, 0.1),
            color=(0.5, 0.5, 0.5, 1)
        )
        self.layout.add_widget(self.debug_label)

        Window.bind(on_key_down=self._on_keyboard_down)

        # --- PATHS ---
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            def callback(permissions, results):
                if all(results):
                    self.start_background_load()
                else:
                    self.label.text = "Permission Denied!\nCannot read files."

            request_permissions(
                [Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE], 
                callback
            )
            self.app_dir = os.path.join("/storage/emulated/0", EXTERNAL_FOLDER_NAME)
        else:
            self.app_dir = os.path.dirname(os.path.abspath(__file__))
            self.start_background_load()

        self.audio_dir = os.path.join(self.app_dir, AUDIO_SUBFOLDER)
        self.db_path = os.path.join(self.app_dir, 'progress.json')

        return self.layout

    def start_background_load(self):
        self.label.text = "Scanning Files...\n(Please Wait)"
        # Run load_data in a separate thread so UI doesn't freeze
        threading.Thread(target=self.load_data).start()

    def load_data(self):
        try:
            # 1. Load Existing DB
            if os.path.exists(self.db_path):
                try:
                    with open(self.db_path, 'r') as f:
                        self.db = json.load(f)
                except: self.db = {}
            else: self.db = {}

            # 2. Scan Files (INCREMENTAL MODE)
            if os.path.exists(self.audio_dir):
                self.update_debug(f"Reading directory...")
                all_files = os.listdir(self.audio_dir)
                
                # Filter for Audio
                all_audio = [f for f in all_files if f.endswith(('.mp3', '.wav', '.ogg'))]
                
                # Filter for 'A' files (Questions)
                a_files = sorted([f for f in all_audio if "_A_" in f])
                
                new_added = 0
                
                # Only scan until we find 'NEW_CARDS_PER_LAUNCH' new items
                for f_a in a_files:
                    if new_added >= NEW_CARDS_PER_LAUNCH:
                        break # Stop scanning to save time/memory

                    parts = f_a.split("_A_")
                    word_id = parts[0]
                    
                    if word_id not in self.db:
                        # Find Match B
                        match_b = next((x for x in all_audio if x.startswith(word_id) and "_B_" in x), None)
                        file_b = match_b if match_b else f_a

                        self.db[word_id] = {
                            "box": 0, "due": 0,
                            "file_a": os.path.join(self.audio_dir, f_a),
                            "file_b": os.path.join(self.audio_dir, file_b)
                        }
                        new_added += 1
                
                if new_added > 0:
                    self.save_db()
                    self.update_debug(f"Added {new_added} new cards.")
                else:
                    self.update_debug("No new cards added.")
                
                # Done scanning, build queue on main thread
                Clock.schedule_once(self.build_session_queue, 0)

            else:
                self.show_error(f"Folder Missing:\n{self.audio_dir}")

        except Exception as e:
            self.show_error(f"Crash in Loader:\n{str(e)}")

    @mainthread
    def update_debug(self, text):
        self.debug_label.text = text

    @mainthread
    def show_error(self, text):
        self.label.text = f"[color=ff0000]{text}[/color]"

    def save_db(self):
        try:
            with open(self.db_path, 'w') as f:
                json.dump(self.db, f)
        except Exception as e:
            print(f"Save failed: {e}")

    @mainthread
    def build_session_queue(self, dt=None):
        now = time.time()
        
        # Get Due Cards
        due = [k for k, v in self.db.items() if v.get('due', 0) <= now and 0 < v['box'] < 3]
        
        # Get New Cards
        new_cards = [k for k, v in self.db.items() if v['box'] == 0]
        new_cards.sort() 
        
        # Fill Queue
        slots = SESSION_LIMIT - len(due)
        if slots > 0:
            self.queue = due + new_cards[:slots]
        else:
            self.queue = due[:SESSION_LIMIT]
        
        random.shuffle(self.queue)
        
        if self.queue:
            self.label.text = f"Ready: {len(self.queue)} Cards\n\n[Press NEXT / VOL UP]"
            self.state = "IDLE"
        else:
            self.label.text = "Session Complete!\nNo cards due."

    def play_audio(self, filepath):
        if self.sound:
            try: self.sound.stop()
            except: pass
        
        if os.path.exists(filepath):
            self.sound = SoundLoader.load(filepath)
            if self.sound: self.sound.play()

    def get_text(self, filepath):
        name = os.path.basename(filepath)
        if "_A_" in name: return name.split("_A_")[-1].replace(".mp3", "").replace("_", " ")
        if "_B_" in name: return name.split("_B_")[-1].replace(".mp3", "").replace("_", " ")
        return name

    def next_step(self):
        if not self.queue and not self.current_card:
            self.label.text = "Session Complete!"
            return

        if self.state == "IDLE" or self.state == "FINISHED_CARD":
            if not self.queue:
                self.label.text = "Session Complete!"
                return
            
            self.current_card = self.queue.pop(0)
            self.state = "PLAYING_Q"
            
            data = self.db[self.current_card]
            self.label.text = f"[b]{self.get_text(data['file_a'])}[/b]\n(Box {data['box']})"
            self.label.color = (1, 1, 1, 1)
            self.play_audio(data['file_a'])

        elif self.state == "PLAYING_Q":
            self.state = "PLAYING_A"
            data = self.db[self.current_card]
            self.label.text = f"[b]ANSWER[/b]\n{self.get_text(data['file_b'])}"
            self.label.color = (1, 1, 0, 1)
            self.play_audio(data['file_b'])

        elif self.state == "PLAYING_A":
            self.grade_card(success=False)

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

        # Save in background to avoid lag
        threading.Thread(target=self.save_db).start()

        self.state = "FINISHED_CARD"
        self.next_step()

    def _on_keyboard_down(self, window, keycode, scancode, text, modifiers):
        key_id = keycode[0] if isinstance(keycode, tuple) else keycode
        if key_id in [276, 25]: # Left / Vol Down
            self.mark_as_known()
            return True
        elif key_id in [275, 24, 32, 13]: # Right / Vol Up / Space
            self.next_step()
            return True
        return False

if __name__ == '__main__':
    DriveLearnApp().run()
