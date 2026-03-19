import json
import os
import time
import random
import threading
from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.core.window import Window
from kivy.core.audio import SoundLoader
from kivy.clock import Clock, mainthread
from kivy.utils import platform

# ================= CONFIGURATION =================
EXTERNAL_FOLDER_NAME = "DriveLearn"
AUDIO_SUBFOLDER = "audio_files"

# 6 Boxes: 0(New/Fail), 1(1d), 2(4d), 3(7d), 4(30d), 5(Mastered)
INTERVALS = [0, 1, 4, 7, 30, 36500] 
SESSION_LIMIT = 15
NEW_CARDS_PER_LAUNCH = 50
# =================================================

class DriveLearnApp(App):
    def build(self):
        self.state = "IDLE" 
        self.queue = []
        self.history = []
        self.current_card = None
        self.sound = None
        self.db = {}
        self.run_mode_active = False
        self.in_settings = False

        Window.allow_screensaver = False
        Window.clearcolor = (0.1, 0.1, 0.1, 1)

        self.root = BoxLayout(orientation='vertical')

        # ================= MAIN UI =================
        self.main_ui = BoxLayout(orientation='vertical', padding=20, spacing=20)
        
        self.label = Label(text="Initializing...", font_size='32sp', halign="center", valign="middle", markup=True, size_hint=(1, 0.5))
        self.label.bind(size=self.label.setter('text_size'))
        self.main_ui.add_widget(self.label)

        self.btn_run_mode = Button(text="ENTER RUN MODE\n(Black Screen)", font_size='20sp', background_color=(0.3, 0.3, 0.3, 1), size_hint=(1, 0.2))
        self.btn_run_mode.bind(on_press=self.toggle_run_mode)
        self.main_ui.add_widget(self.btn_run_mode)

        self.btn_settings = Button(text="SETTINGS & STATS", font_size='20sp', background_color=(0.2, 0.4, 0.6, 1), size_hint=(1, 0.15))
        self.btn_settings.bind(on_press=self.open_settings)
        self.main_ui.add_widget(self.btn_settings)

        self.debug_label = Label(text="System Ready", font_size='14sp', size_hint=(1, 0.1), color=(0.5, 0.5, 0.5, 1))
        self.main_ui.add_widget(self.debug_label)

        # ================= SETTINGS UI =================
        self.settings_ui = BoxLayout(orientation='vertical', padding=30, spacing=20)
        
        self.stats_label = Label(text="Loading stats...", font_size='18sp', halign="center", valign="middle", size_hint=(1, 0.6), markup=True)
        self.stats_label.bind(size=self.stats_label.setter('text_size'))
        self.settings_ui.add_widget(self.stats_label)

        # Wipe Protection Row
        self.wipe_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint=(1, 0.2))
        self.btn_init_wipe = Button(text="WIPE PROGRESS", background_color=(0.8, 0, 0, 1))
        self.btn_init_wipe.bind(on_press=self.show_wipe_confirm)
        
        self.wipe_input = TextInput(hint_text="Type 'clear'", multiline=False, opacity=0, disabled=True, font_size='18sp')
        self.btn_confirm_wipe = Button(text="CONFIRM WIPE", background_color=(1, 0, 0, 1), opacity=0, disabled=True)
        self.btn_confirm_wipe.bind(on_press=self.execute_wipe)

        self.wipe_layout.add_widget(self.btn_init_wipe)
        self.wipe_layout.add_widget(self.wipe_input)
        self.wipe_layout.add_widget(self.btn_confirm_wipe)
        self.settings_ui.add_widget(self.wipe_layout)

        self.btn_back = Button(text="BACK TO SESSION", size_hint=(1, 0.2), background_color=(0.3, 0.3, 0.3, 1))
        self.btn_back.bind(on_press=self.close_settings)
        self.settings_ui.add_widget(self.btn_back)

        # Start with Main UI
        self.root.add_widget(self.main_ui)

        Window.bind(on_key_down=self._on_keyboard_down)

        # ================= BOOTUP =================
        if platform == 'android':
            self.app_dir = os.path.join("/storage/emulated/0", EXTERNAL_FOLDER_NAME)
            self.request_storage_access()
        else:
            self.app_dir = os.path.dirname(os.path.abspath(__file__))
            self.start_background_load()

        self.audio_dir = os.path.join(self.app_dir, AUDIO_SUBFOLDER)
        self.db_path = os.path.join(self.app_dir, 'progress.json')

        return self.root

    # ================= SETTINGS LOGIC =================
    def open_settings(self, instance):
        self.in_settings = True
        if self.sound: self.sound.stop()
        self.root.clear_widgets()
        self.root.add_widget(self.settings_ui)
        self.load_stats()
        
        self.btn_init_wipe.text = "WIPE PROGRESS"
        self.btn_init_wipe.disabled = False
        self.wipe_input.text = ""
        self.wipe_input.hint_text = "Type 'clear'"
        self.wipe_input.opacity = 0
        self.wipe_input.disabled = True
        self.btn_confirm_wipe.opacity = 0
        self.btn_confirm_wipe.disabled = True

    def close_settings(self, instance):
        self.in_settings = False
        self.root.clear_widgets()
        self.root.add_widget(self.main_ui)
        if self.queue:
            self.label.text = f"Queue: {len(self.queue)} Cards\n\n[Press Remote to Resume]"
            self.state = "IDLE"

    def show_wipe_confirm(self, instance):
        self.btn_init_wipe.text = "Type 'clear' ->"
        self.btn_init_wipe.disabled = True
        self.wipe_input.opacity = 1
        self.wipe_input.disabled = False
        self.btn_confirm_wipe.opacity = 1
        self.btn_confirm_wipe.disabled = False

    def execute_wipe(self, instance):
        if self.wipe_input.text.strip().lower() == 'clear':
            if os.path.exists(self.db_path):
                try: os.remove(self.db_path)
                except: pass
            
            self.db = {}
            self.queue = []
            self.history = []
            self.current_card = None
            self.state = "IDLE"
            
            self.stats_label.text = "[color=00ff00]DATA SUCCESSFULLY CLEARED![/color]\n\nAudio files remain, but all progress is reset."
            self.wipe_input.opacity = 0
            self.wipe_input.disabled = True
            self.btn_confirm_wipe.opacity = 0
            self.btn_confirm_wipe.disabled = True
            self.btn_init_wipe.text = "WIPED"
            
            # Restart queue instantly
            Clock.schedule_once(self.build_session_queue, 0)
        else:
            self.wipe_input.text = ""
            self.wipe_input.hint_text = "Must type 'clear'!"

    def load_stats(self):
        counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for data in self.db.values():
            box = data.get('box', 0)
            if box in counts: counts[box] += 1
            
        self.stats_label.text = (
            f"[b]TOTAL WORDS TRACKED: {len(self.db)}[/b]\n\n"
            f"Box 0 (New/Fail): {counts[0]}\n"
            f"Box 1 (1 Day): {counts[1]}\n"
            f"Box 2 (4 Days): {counts[2]}\n"
            f"Box 3 (7 Days): {counts[3]}\n"
            f"Box 4 (30 Days): {counts[4]}\n"
            f"Box 5 (Mastered): {counts[5]}"
        )

    # ================= CORE APP LOGIC =================
    def request_storage_access(self):
        from jnius import autoclass
        Build = autoclass('android.os.Build$VERSION')
        
        if Build.SDK_INT >= 30:
            Environment = autoclass('android.os.Environment')
            if not Environment.isExternalStorageManager():
                Intent = autoclass('android.content.Intent')
                Settings = autoclass('android.provider.Settings')
                Uri = autoclass('android.net.Uri')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                
                intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
                uri = Uri.parse("package:" + PythonActivity.mActivity.getPackageName())
                intent.setData(uri)
                PythonActivity.mActivity.startActivity(intent)
                
                self.label.text = "[color=ffff00]ACTION REQUIRED:[/color]\n\nPlease toggle 'Allow' in the settings menu that just opened.\n\n[b]Then restart this app.[/b]"
                return
                
        from android.permissions import request_permissions, Permission
        def callback(permissions, results):
            self.start_background_load()
        request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE], callback)

    def toggle_run_mode(self, instance=None):
        self.run_mode_active = not self.run_mode_active
        if self.run_mode_active:
            Window.clearcolor = (0, 0, 0, 1)
            self.label.opacity = 0
            self.btn_run_mode.opacity = 0
            self.btn_settings.opacity = 0
            self.debug_label.opacity = 0
        else:
            Window.clearcolor = (0.1, 0.1, 0.1, 1)
            self.label.opacity = 1
            self.btn_run_mode.opacity = 1
            self.btn_settings.opacity = 1
            self.debug_label.opacity = 1

    def start_background_load(self):
        self.label.text = "Scanning Files..."
        threading.Thread(target=self.load_data).start()

    def load_data(self):
        try:
            if os.path.exists(self.db_path):
                try:
                    with open(self.db_path, 'r') as f:
                        self.db = json.load(f)
                except Exception as e: 
                    self.update_debug(f"DB Load Error: {e}")
                    self.db = {}
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
                self.show_error("Audio Folder Missing")
        except Exception as e:
            self.show_error(f"Crash: {e}")

    @mainthread
    def show_error(self, text):
        self.label.text = f"[color=ff0000]{text}[/color]"

    @mainthread
    def update_debug(self, text):
        self.debug_label.text = text

    def save_db(self):
        try:
            with open(self.db_path, 'w') as f:
                json.dump(self.db, f)
            self.update_debug("Progress saved successfully.")
        except Exception as e:
            self.update_debug(f"SAVE BLOCKED: {str(e)}")

    @mainthread
    def build_session_queue(self, dt=None):
        now = time.time()
        due = [k for k, v in self.db.items() if v.get('due', 0) <= now and 0 < v['box'] < 5]
        due.sort(key=lambda k: (self.db[k]['box'], self.db[k]['due']))
        
        new_cards = [k for k, v in self.db.items() if v['box'] == 0]
        new_cards.sort() 
        
        slots = SESSION_LIMIT - len(due)
        if slots > 0:
            self.queue = due + new_cards[:slots]
        else:
            self.queue = due[:SESSION_LIMIT]
            
        random.shuffle(self.queue)
        
        if self.queue:
            if not self.in_settings:
                self.label.text = f"Queue: {len(self.queue)} Cards\n\n[Press Remote to Start]"
            self.state = "IDLE"
        else:
            self.label.text = "Session Complete!"

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

    def refill_queue(self):
        now = time.time()
        active_ids = set(self.queue)
        if self.current_card: active_ids.add(self.current_card)
        
        due = [k for k, v in self.db.items() if v.get('due', 0) <= now and 0 < v['box'] < 5 and k not in active_ids]
        due.sort(key=lambda k: (self.db[k]['box'], self.db[k]['due']))
        
        if due:
            self.queue.append(due[0])
            return

        new_cards = [k for k, v in self.db.items() if v['box'] == 0 and k not in active_ids]
        new_cards.sort()
        if new_cards:
            self.queue.append(new_cards[0])

    def next_step(self):
        if not self.queue and not self.current_card: return

        if self.state == "IDLE" or self.state == "FINISHED_CARD":
            if self.current_card: self.history.append(self.current_card)
            
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

    def rewind_action(self):
        if self.sound: self.sound.stop()

        if self.state == "PLAYING_A":
            self.state = "PLAYING_Q"
            data = self.db[self.current_card]
            self.label.text = f"[b]{self.get_text(data['file_a'])}[/b]\n(Box {data['box']})"
            self.label.color = (1, 1, 1, 1)
            self.play_audio(data['file_a'])

        elif self.state == "PLAYING_Q" or self.state == "IDLE":
            if not self.history: return
            if self.current_card: self.queue.insert(0, self.current_card)
            self.current_card = self.history.pop()
            
            self.state = "PLAYING_Q"
            data = self.db[self.current_card]
            self.label.text = f"<< REWINDING\n[b]{self.get_text(data['file_a'])}[/b]"
            self.play_audio(data['file_a'])

    def mark_as_known(self):
        if self.current_card:
            self.label.text = "[b]KNOWN[/b]"
            self.label.color = (0, 1, 0, 1)
            self.grade_card(success=True)

    def grade_card(self, success):
        if not self.current_card: return
        data = self.db[self.current_card]
        
        if success:
            data['box'] += 1
            if data['box'] >= len(INTERVALS): data['box'] = len(INTERVALS) - 1
        else:
            data['box'] = 0 
        
        wait_days = INTERVALS[data['box']]
        if not success:
            data['due'] = time.time() + 300
            self.queue.append(self.current_card) 
        else:
            data['due'] = time.time() + (wait_days * 86400)

        threading.Thread(target=self.save_db).start()
        
        self.refill_queue()
        self.state = "FINISHED_CARD"
        self.next_step()

    def _on_keyboard_down(self, window, keycode, scancode, text, modifiers):
        # Ignore flashcard remote commands if we are in the settings screen
        if self.in_settings: return False

        key_id = keycode[0] if isinstance(keycode, tuple) else keycode
        
        if key_id in [276, 25]: 
            self.mark_as_known()
            return True

        elif key_id in [273, 275, 24, 32, 13]: 
            self.next_step()
            return True

        elif key_id == 274:
            self.rewind_action()
            return True
            
        elif key_id == 27:
            if self.run_mode_active:
                self.toggle_run_mode()
                return True

        return False

if __name__ == '__main__':
    DriveLearnApp().run()
