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
# Box Intervals (Days): 0=Today, 1=Tomorrow, 2=4 days, 3=Forever
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

        # --- UI (Big & High Contrast) ---
        self.layout = BoxLayout(orientation='vertical', padding=20)
        self.label = Label(
            text="Loading...", 
            font_size='40sp', 
            halign="center", 
            valign="middle", 
            markup=True
        )
        self.label.bind(size=self.label.setter('text_size'))
        self.layout.add_widget(self.label)
        
        # --- INPUT BINDING ---
        Window.bind(on_key_down=self._on_keyboard_down)

        # --- PATHS ---
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])
            self.app_dir = os.path.join("/storage/emulated/0", EXTERNAL_FOLDER_NAME)
        else:
            self.app_dir = os.path.dirname(os.path.abspath(__file__))

        self.audio_dir = os.path.join(self.app_dir, 'audio_files')
        self.db_path = os.path.join(self.app_dir, 'progress.json')

        Clock.schedule_once(self.load_data, 1)
        return self.layout

    def load_data(self, dt=None):
        # 1. Load DB
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r') as f:
                    self.db = json.load(f)
            except: self.db = {}
        else: self.db = {}

        # 2. Scan Files
        if os.path.exists(self.audio_dir):
            all_files = os.listdir(self.audio_dir)
            a_files = sorted([f for f in all_files if "_A_" in f and f.endswith(('.mp3', '.wav', '.ogg'))])
            
            for f_a in a_files:
                word_id = f_a.split("_")[0]
                matching_b = next((x for x in all_files if x.startswith(word_id) and "_B_" in x), None)
                file_b = matching_b if matching_b else f_a 

                if word_id not in self.db:
                    self.db[word_id] = {
                        "box": 0, "due": 0,
                        "file_a": os.path.join(self.audio_dir, f_a),
                        "file_b": os.path.join(self.audio_dir, file_b)
                    }
        else:
            self.label.text = f"ERROR: Folder missing\n{EXTERNAL_FOLDER_NAME}/audio_files"
            return
        
        self.build_session_queue()

    def build_session_queue(self):
        now = time.time()
        # Get due cards + new cards
        due = [k for k, v in self.db.items() if v.get('due', 0) <= now and 0 < v['box'] < 3]
        new = [k for k, v in self.db.items() if v['box'] == 0]
        
        self.queue = due + new[:SESSION_LIMIT - len(due)]
        random.shuffle(self.queue)
        
        if self.queue:
            self.label.text = f"Ready: {len(self.queue)} Cards\n\n[Press NEXT to Start]"
        else:
            self.label.text = "All Done!\nNo cards due."

    def play_audio(self, filepath):
        if self.sound:
            try: self.sound.stop()
            except: pass
        if os.path.exists(filepath):
            self.sound = SoundLoader.load(filepath)
            if self.sound: self.sound.play()

    # --- CORE LOGIC ---

    def next_step(self):
        """ The main 'Forward' loop """
        if not self.queue and not self.current_card:
            self.label.text = "Session Complete!"
            return

        # State Machine
        if self.state == "IDLE" or self.state == "FINISHED_CARD":
            # START NEW CARD
            if not self.queue:
                self.label.text = "Session Complete!"
                return
            self.current_card = self.queue.pop(0)
            self.state = "PLAYING_Q"
            
            # Show/Play Question
            data = self.db[self.current_card]
            self.label.text = f"[b]?[/b]\n(Box {data['box']})"
            self.label.color = (1, 1, 1, 1) # White
            self.play_audio(data['file_a'])

        elif self.state == "PLAYING_Q":
            # SHOW ANSWER
            self.state = "PLAYING_A"
            data = self.db[self.current_card]
            self.label.text = f"[b]ANSWER[/b]\n(Box {data['box']})"
            self.label.color = (1, 1, 0, 1) # Yellow
            self.play_audio(data['file_b'])

        elif self.state == "PLAYING_A":
            # FINISH CARD (DEFAULT = FAIL/REPEAT)
            # If user presses NEXT here, it means they didn't press "Good", so we keep it in Box 0
            self.grade_card(success=False)

    def mark_as_known(self):
        """ The 'I Know It' Shortcut (Left Key) """
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
            data['box'] = 1 # Reset to learning
        
        # Calculate next due date
        wait_days = INTERVALS[data['box']]
        if not success:
            data['due'] = time.time() + 300 # Show again in 5 mins
            self.queue.append(self.current_card) # Add to back of queue immediately
        else:
            data['due'] = time.time() + (wait_days * 86400)

        # Save
        with open(self.db_path, 'w') as f:
            json.dump(self.db, f)

        self.state = "FINISHED_CARD"
        self.next_step() # Auto-load next card

    def _on_keyboard_down(self, window, keycode, scancode, text, modifiers):
        key_id = keycode[0] if isinstance(keycode, tuple) else keycode
        
        # === KEY LEFT (276) / VOLUME DOWN (25) ===
        # "I Know It" -> Marks Good, Skips to Next
        if key_id in [276, 25]: 
            self.mark_as_known()
            return True

        # === KEY RIGHT (275) / VOLUME UP (24) / SPACE (32) ===
        # "Next Step" -> Question -> Answer -> Next (Fail)
        elif key_id in [275, 24, 32, 13]: 
            self.next_step()
            return True
            
        return False

if __name__ == '__main__':
    DriveLearnApp().run()
