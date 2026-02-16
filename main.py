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

# ================= CONFIGURATION =================
# Box 0 = New/Fail (Show Today)
# Box 1 = Learning (Show Tomorrow)
# Box 2 = Review (Show in 4 Days)
# Box 3 = Retired (Never Show Again / 100 years)
INTERVALS = [0, 1, 4, 36500] 

SESSION_LIMIT = 20      
RANDOMIZE_QUEUE = True  
# =================================================

class DriveLearnApp(App):
    def build(self):
        self.state = "IDLE" 
        self.queue = []
        self.history = [] 
        self.current_card = None
        self.sound = None
        
        # Increased font size for better visibility
        self.layout = BoxLayout(orientation='vertical', padding=20)
        self.label = Label(text="Loading...", font_size='36sp', halign="center", markup=True)
        self.layout.add_widget(self.label)
        
        Window.bind(on_key_down=self._on_keyboard_down)
        self.load_data()
        return self.layout

    def load_data(self):
        self.app_dir = os.path.dirname(os.path.abspath(__file__))
        self.audio_dir = os.path.join(self.app_dir, 'audio_files')
        self.db_path = os.path.join(self.app_dir, 'progress.json')

        if os.path.exists(self.db_path):
            with open(self.db_path, 'r') as f:
                self.db = json.load(f)
        else:
            self.db = {}

        if os.path.exists(self.audio_dir):
            new_count = 0
            # Get all files first
            all_files = os.listdir(self.audio_dir)
            
            # Filter for A files
            a_files = sorted([f for f in all_files if "_A_" in f and f.endswith(".mp3")])
            
            for f_a in a_files:
                # Extract ID (e.g. "0001")
                word_id = f_a.split("_")[0]
                
                # SMART MATCH: Find the matching B file in the list
                # Look for a file that starts with the same ID but contains "_B_"
                matching_b = next((x for x in all_files if x.startswith(word_id) and "_B_" in x), None)
                
                # Default to constructed name if not found (fallback)
                if matching_b:
                    file_b_path = os.path.join(self.audio_dir, matching_b)
                else:
                    file_b_path = os.path.join(self.audio_dir, f"{word_id}_B_Eng.mp3")

                if word_id not in self.db:
                    self.db[word_id] = {
                        "box": 0, 
                        "due": 0,
                        "file_a": os.path.join(self.audio_dir, f_a),
                        "file_b": file_b_path
                    }
                    new_count += 1
            
            if new_count > 0:
                print(f"Added {new_count} new words.")
        
        self.build_session_queue()

    def build_session_queue(self):
        now = time.time()
        
        due_reviews = [k for k, v in self.db.items() if v['due'] <= now and v['box'] > 0 and v['box'] < 3]
        new_cards = [k for k, v in self.db.items() if v['box'] == 0]
        new_cards.sort() 

        self.queue = []
        self.queue.extend(due_reviews)
        
        slots_remaining = SESSION_LIMIT - len(self.queue)
        if slots_remaining > 0:
            self.queue.extend(new_cards[:slots_remaining])
        
        if RANDOMIZE_QUEUE:
            random.shuffle(self.queue)
        
        total_count = len(self.queue)
        if total_count > 0:
            self.label.text = f"Session Ready!\n{total_count} Cards\n\n[Press UP to Start]"
        else:
            self.label.text = "You are all caught up!\nNo cards due today."

    def save_db(self):
        with open(self.db_path, 'w') as f:
            json.dump(self.db, f)

    def stop_current_audio(self):
        if self.sound:
            try:
                self.sound.unbind(on_stop=self.on_audio_finish)
                self.sound.stop()
                self.sound.unload()
            except:
                pass
            self.sound = None

    def play_audio(self, filepath):
        self.stop_current_audio()
        if os.path.exists(filepath):
            self.sound = SoundLoader.load(filepath)
            if self.sound:
                self.sound.bind(on_stop=self.on_audio_finish)
                self.sound.play()
        else:
            print(f"File missing: {filepath}")

    def on_audio_finish(self, dt):
        # Pause after Question and wait for user
        if self.state == "PLAYING_Q":
            pass # Do nothing, just wait.

    def extract_display_word(self, filepath, is_answer=False):
        """Attempts to pull a readable word from the filename"""
        filename = os.path.basename(filepath)
        word = ""
        
        if "_A_" in filename:
            # 0001_A_Gato.mp3 -> Gato
            parts = filename.split("_A_")
            if len(parts) > 1:
                word = parts[1].replace(".mp3", "").replace("_", " ")
        elif "_B_" in filename:
            # 0001_B_Eng_Cat.mp3 -> Cat
            # 0001_B_Eng.mp3 -> English Audio
            parts = filename.split("_B_")
            if len(parts) > 1:
                raw = parts[1].replace(".mp3", "").replace("_", " ")
                if raw.lower().strip() == "eng":
                    word = "[English Audio]"
                else:
                    word = raw.replace("Eng", "") # Remove "Eng" prefix if present
        
        return word if word else "Unknown"

    def play_answer(self):
        self.state = "PLAYING_A"
        if self.current_card:
            data = self.db[self.current_card]
            self.play_audio(data['file_b'])
            
            # Get words
            word_a = self.extract_display_word(data['file_a'])
            word_b = self.extract_display_word(data['file_b'], is_answer=True)
            
            box = data['box']
            # DISPLAY BOTH: Spanish (Top) and English (Bottom)
            self.label.text = f"[color=888888]{word_a}[/color]\n\n[b][color=00ff00]{word_b}[/color][/b]\n\n(Box {box})"

    def next_card(self):
        if self.current_card:
            self.history.append(self.current_card)

        if not self.queue:
            self.label.text = "Session Complete!\nGreat job."
            self.state = "IDLE"
            self.current_card = None
            return

        self.current_card = self.queue.pop(0)
        self.play_current_card_fresh()

    def undo_card(self):
        if not self.history:
            if self.current_card: self.play_current_card_fresh()
            return

        self.stop_current_audio()
        if self.current_card:
            self.queue.insert(0, self.current_card)
        
        self.current_card = self.history.pop()
        self.label.text = "<< REWINDING"
        Clock.schedule_once(lambda dt: self.play_current_card_fresh(), 0.1)

    def play_current_card_fresh(self):
        self.state = "PLAYING_Q"
        word_a = self.extract_display_word(self.db[self.current_card]['file_a'])
        box = self.db[self.current_card]['box']
        
        # Show Spanish only
        self.label.text = f"[b]{word_a}[/b]\n\n(Box {box})\n\n[UP] = Reveal"
        self.play_audio(self.db[self.current_card]['file_a'])

    def grade_card(self, success):
        if not self.current_card: return
        
        data = self.db[self.current_card]
        if success:
            data['box'] += 1
            if data['box'] >= len(INTERVALS): data['box'] = len(INTERVALS) - 1
            self.label.text = "[color=00ff00]GOOD![/color]"
        else:
            data['box'] = 1
            self.label.text = "[color=ff0000]AGAIN...[/color]"
        
        wait_days = INTERVALS[data['box']]
        if not success:
            data['due'] = time.time() + 300
        else:
            data['due'] = time.time() + (wait_days * 86400)

        self.save_db()
        self.next_card()

    def _on_keyboard_down(self, window, keycode, scancode, text, modifiers):
        key_id = keycode[0] if isinstance(keycode, tuple) else keycode

        # UP ARROW / SPACE
        if key_id in [273, 32]: 
            if self.state == "IDLE":
                self.next_card()
            elif self.state == "PLAYING_Q":
                self.play_answer()
            elif self.state == "PLAYING_A":
                self.grade_card(success=False)
            return True

        # DOWN ARROW / BACKSPACE (Rewind)
        elif key_id in [274, 8, 27]: 
            self.undo_card()
            return True

        # LEFT ARROW (Long Press = Good)
        elif key_id == 276: 
            if self.state in ["PLAYING_Q", "PLAYING_A"]:
                self.grade_card(success=True)
            return True
            
        return False

if __name__ == '__main__':
    DriveLearnApp().run()
