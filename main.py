import json
import os
import time
import random
from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.core.window import Window
from kivy.core.audio import SoundLoader
from kivy.clock import Clock
from kivy.utils import platform

# ================= CONFIGURATION =================
EXTERNAL_FOLDER_NAME = "DriveLearn"
AUDIO_SUBFOLDER = "audio_files"
INTERVALS = [0, 1, 4, 36500] 
SESSION_LIMIT = 50
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
        
        # Debug Label (Shows path/count)
        self.debug_label = Label(
            text="Path Check...", 
            font_size='12sp', 
            size_hint=(1, 0.1),
            color=(0.5, 0.5, 0.5, 1)
        )
        self.layout.add_widget(self.debug_label)

        Window.bind(on_key_down=self._on_keyboard_down)

        # --- PATHS ---
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])
            self.app_dir = os.path.join("/storage/emulated/0", EXTERNAL_FOLDER_NAME)
        else:
            self.app_dir = os.path.dirname(os.path.abspath(__file__))

        self.audio_dir = os.path.join(self.app_dir, AUDIO_SUBFOLDER)
        self.db_path = os.path.join(self.app_dir, 'progress.json')

        Clock.schedule_once(self.load_data, 1)
        return self.layout

    def load_data(self, dt=None):
        # 1. Load Existing DB
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r') as f:
                    self.db = json.load(f)
            except: self.db = {}
        else: self.db = {}

        # 2. FORCE RESCAN FILES
        if os.path.exists(self.audio_dir):
            all_files = os.listdir(self.audio_dir)
            # Filter specifically for _A_ files
            a_files = sorted([f for f in all_files if "_A_" in f and f.endswith(('.mp3', '.wav', '.ogg'))])
            
            new_count = 0
            for f_a in a_files:
                # Extract ID "0001" from "0001_A_..."
                parts = f_a.split("_A_")
                word_id = parts[0]
                
                # Check if this ID is already in DB. If NOT, add it.
                if word_id not in self.db:
                    # Look for matching B file
                    matching_b = next((x for x in all_files if x.startswith(word_id) and "_B_" in x), None)
                    
                    # If B found, use it. If not, fallback to A.
                    file_b_path = os.path.join(self.audio_dir, matching_b) if matching_b else os.path.join(self.audio_dir, f_a)
                    file_a_path = os.path.join(self.audio_dir, f_a)

                    self.db[word_id] = {
                        "box": 0, 
                        "due": 0,
                        "file_a": file_a_path,
                        "file_b": file_b_path
                    }
                    new_count += 1
            
            self.debug_label.text = f"Files: {len(a_files)} | DB: {len(self.db)} | New: {new_count}"
            
            # Save if we found new stuff
            if new_count > 0:
                with open(self.db_path, 'w') as f:
                    json.dump(self.db, f)

        else:
            self.label.text = f"ERROR: Folder Missing!\n{self.audio_dir}"
            return
        
        self.build_session_queue()

    def build_session_queue(self):
        now = time.time()
        
        # 1. Get Due Cards (Review)
        due = [k for k, v in self.db.items() if v.get('due', 0) <= now and 0 < v['box'] < 3]
        
        # 2. Get New Cards (Box 0)
        new_cards = [k for k, v in self.db.items() if v['box'] == 0]
        # Sort new cards by ID so 0001 comes before 0002
        new_cards.sort() 
        
        # Combine: Due first, then fill remaining slots with New
        slots_needed = SESSION_LIMIT - len(due)
        if slots_needed > 0:
            self.queue = due + new_cards[:slots_needed]
        else:
            self.queue = due[:SESSION_LIMIT]
        
        # Shuffle specifically for the session (so you don't get 1,2,3 in order)
        random.shuffle(self.queue)
        
        if self.queue:
            self.label.text = f"Ready: {len(self.queue)} Cards\n\n[Press NEXT / VOL UP]"
            self.state = "IDLE"
        else:
            self.label.text = "All Done!\nNo cards due."

    def play_audio(self, filepath):
        if self.sound:
            try: self.sound.stop()
            except: pass
        
        if os.path.exists(filepath):
            self.sound = SoundLoader.load(filepath)
            if self.sound: self.sound.play()
        else:
            self.label.text = f"Error: File Missing\n{os.path.basename(filepath)}"

    def get_display_text(self, filepath):
        # Extract "StudyRoot" from "0001_A_StudyRoot.mp3"
        name = os.path.basename(filepath)
        if "_A_" in name: return name.split("_A_")[-1].replace(".mp3", "").replace("_", " ")
        if "_B_" in name: return name.split("_B_")[-1].replace(".mp3", "").replace("_", " ")
        return name

    def next_step(self):
        # State Machine
        if self.state == "IDLE" or self.state == "FINISHED_CARD":
            if not self.queue:
                self.label.text = "Session Complete!"
                return
            
            self.current_card = self.queue.pop(0)
            self.state = "PLAYING_Q"
            
            # Show Question
            data = self.db[self.current_card]
            text = self.get_display_text(data['file_a'])
            self.label.text = f"[b]{text}[/b]\n(Box {data['box']})"
            self.label.color = (1, 1, 1, 1) # White
            self.play_audio(data['file_a'])

        elif self.state == "PLAYING_Q":
            # Show Answer
            self.state = "PLAYING_A"
            data = self.db[self.current_card]
            text = self.get_display_text(data['file_b'])
            self.label.text = f"[b]ANSWER[/b]\n{text}"
            self.label.color = (1, 1, 0, 1) # Yellow
            self.play_audio(data['file_b'])

        elif self.state == "PLAYING_A":
            # Finish Card (Default Fail)
            self.grade_card(success=False)

    def mark_as_known(self):
        if self.current_card:
            self.label.text = "[b]MARKED KNOWN[/b]"
            self.label.color = (0, 1, 0, 1) # Green
            self.grade_card(success=True)

    def grade_card(self, success):
        if not self.current_card: return
        
        data = self.db[self.current_card]
        if success:
            data['box'] += 1
            if data['box'] >= len(INTERVALS): data['box'] = len(INTERVALS) - 1
        else:
            data['box'] = 1 # Reset
        
        wait_days = INTERVALS[data['box']]
        if not success:
            data['due'] = time.time() + 300
            self.queue.append(self.current_card) 
        else:
            data['due'] = time.time() + (wait_days * 86400)

        with open(self.db_path, 'w') as f:
            json.dump(self.db, f)

        self.state = "FINISHED_CARD"
        self.next_step() # Auto-load next

    def _on_keyboard_down(self, window, keycode, scancode, text, modifiers):
        key_id = keycode[0] if isinstance(keycode, tuple) else keycode
        
        # KEY LEFT (276) / VOL DOWN (25) -> I Know It
        if key_id in [276, 25]: 
            self.mark_as_known()
            return True

        # KEY RIGHT (275) / VOL UP (24) / SPACE (32) / ENTER (13) -> Next
        elif key_id in [275, 24, 32, 13]: 
            self.next_step()
            return True
            
        return False

if __name__ == '__main__':
    DriveLearnApp().run()
