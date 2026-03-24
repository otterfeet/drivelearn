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
        self.db = {}
        self.run_mode_active = False
        self.in_settings = False
        
        # Audio Preloader Engine
        self.active_sound = None
        self.preloaded_sound = None
        self.preloaded_path = ""
        
        # Mode Management: True = A->B, False = B->A
        self.play_mode_A_to_B = True

        Window.allow_screensaver = False
        Window.clearcolor = (0.1, 0.1, 0.1, 1)

        self.root = BoxLayout(orientation='vertical')

        # ================= MAIN UI =================
        self.main_ui = BoxLayout(orientation='vertical', padding=20, spacing=20)
        
        self.label = Label(text="Initializing...", font_size='32sp', halign="center", valign="middle", markup=True, size_hint=(1, 0.55))
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
        self.settings_ui = BoxLayout(orientation='vertical', padding=20, spacing=15)
        
        self.stats_label = Label(text="Loading stats...", font_size='18sp', halign="center", valign="middle", size_hint=(1, 0.4), markup=True)
        self.stats_label.bind(size=self.stats_label.setter('text_size'))
        self.settings_ui.add_widget(self.stats_label)

        self.btn_toggle_mode = Button(text="MODE: Front -> Back\n(Tap to swap)", font_size='18sp', background_color=(0.5, 0.3, 0.8, 1), size_hint=(1, 0.15))
        self.btn_toggle_mode.bind(on_press=self.toggle_play_mode)
        self.settings_ui.add_widget(self.btn_toggle_mode)

        # Import / Export Row
        self.backup_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint=(1, 0.15))
        self.btn_export = Button(text="EXPORT BACKUP", background_color=(0.2, 0.6, 0.2, 1))
        self.btn_export.bind(on_press=self.export_data)
        self.btn_import = Button(text="IMPORT BACKUP", background_color=(0.6, 0.4, 0.2, 1))
        self.btn_import.bind(on_press=self.import_data)
        self.backup_layout.add_widget(self.btn_export)
        self.backup_layout.add_widget(self.btn_import)
        self.settings_ui.add_widget(self.backup_layout)

        # Wipe Protection Row
        self.wipe_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint=(1, 0.15))
        self.btn_init_wipe = Button(text="WIPE PROGRESS", background_color=(0.8, 0, 0, 1))
        self.btn_init_wipe.bind(on_press=self.show_wipe_confirm)
        
        self.wipe_input = TextInput(hint_text="Type 'clear'", multiline=False, opacity=0, disabled=True, font_size='18sp')
        self.btn_confirm_wipe = Button(text="CONFIRM WIPE", background_color=(1, 0, 0, 1), opacity=0, disabled=True)
        self.btn_confirm_wipe.bind(on_press=self.execute_wipe)

        self.wipe_layout.add_widget(self.btn_init_wipe)
        self.wipe_layout.add_widget(self.wipe_input)
        self.wipe_layout.add_widget(self.btn_confirm_wipe)
        self.settings_ui.add_widget(self.wipe_layout)

        self.btn_back = Button(text="BACK TO SESSION", size_hint=(1, 0.15), background_color=(0.3, 0.3, 0.3, 1))
        self.btn_back.bind(on_press=self.close_settings)
        self.settings_ui.add_widget(self.btn_back)

        self.root.add_widget(self.main_ui)
        Window.bind(on_key_down=self._on_keyboard_down)

        # ================= BOOTUP =================
        if platform == 'android':
            self.app_dir = os.path.join("/storage/emulated/0", EXTERNAL_FOLDER_NAME)
        else:
            self.app_dir = os.path.dirname(os.path.abspath(__file__))
            
        self.audio_dir = os.path.join(self.app_dir, AUDIO_SUBFOLDER)
        self.db_path = os.path.join(self.app_dir, 'progress.json')

        if platform == 'android':
            self.request_storage_access()
        else:
            self.start_background_load()

        return self.root

    # ================= UNIFIED DB HELPER =================
    def get_mode_data(self, card_id):
        """Returns the specific tracking stats based on the current mode"""
        data = self.db[card_id]
        return data['a_to_b'] if self.play_mode_A_to_B else data['b_to_a']

    # ================= MODE TOGGLE =================
    def toggle_play_mode(self, instance):
        self.play_mode_A_to_B = not self.play_mode_A_to_B
        
        if self.play_mode_A_to_B:
            self.btn_toggle_mode.text = "MODE: Front -> Back\n(Tap to swap)"
        else:
            self.btn_toggle_mode.text = "MODE: Back -> Front\n(Tap to swap)"

        if self.active_sound: self.active_sound.stop()
        self.queue = []
        self.history = []
        self.current_card = None
        self.state = "IDLE"
        
        Clock.schedule_once(self.build_session_queue, 0)
        self.load_stats()

    # ================= SETTINGS LOGIC =================
    def open_settings(self, instance):
        self.in_settings = True
        if self.active_sound: self.active_sound.stop()
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

    # ================= IMPORT & EXPORT =================
    def export_data(self, instance):
        backup_path = os.path.join(self.app_dir, 'progress_backup.json')
        try:
            with open(backup_path, 'w') as f:
                json.dump(self.db, f)
            self.stats_label.text = f"[color=00ff00]BACKUP SAVED TO FOLDER![/color]\n\n" + self.stats_label.text
        except Exception as e:
            self.stats_label.text = f"[color=ff0000]Export Failed: {e}[/color]\n\n" + self.stats_label.text

    def import_data(self, instance):
        backup_path = os.path.join(self.app_dir, 'progress_backup.json')
        if os.path.exists(backup_path):
            try:
                with open(backup_path, 'r') as f:
                    self.db = json.load(f)
                self.save_db()
                self.queue = []
                self.current_card = None
                self.state = "IDLE"
                Clock.schedule_once(self.build_session_queue, 0)
                self.load_stats()
                self.stats_label.text = f"[color=00ff00]BACKUP RESTORED SUCCESSFULLY![/color]\n\n" + self.stats_label.text
            except Exception as e:
                self.stats_label.text = f"[color=ff0000]Import Failed: {e}[/color]\n\n" + self.stats_label.text
        else:
            self.stats_label.text = f"[color=ffff00]No 'progress_backup.json' found in folder![/color]\n\n" + self.stats_label.text

    def show_wipe_confirm(self, instance):
        self.btn_init_wipe.text = "Type 'clear' ->"
        self.btn_init_wipe.disabled = True
        self.wipe_input.opacity = 1
        self.wipe_input.disabled = False
        self.btn_confirm_wipe.opacity = 1
        self.btn_confirm_wipe.disabled = False

    def execute_wipe(self, instance):
        if self.wipe_input.text.strip().lower() == 'clear':
            # Wipe ONLY the current mode's progress
            for word_id, data in self.db.items():
                if self.play_mode_A_to_B:
                    data['a_to_b'] = {"box": 0, "due": 0}
                else:
                    data['b_to_a'] = {"box": 0, "due": 0}
                    
            self.save_db()
            self.queue = []
            self.history = []
            self.current_card = None
            self.state = "IDLE"
            
            Clock.schedule_once(self.build_session_queue, 0)
            self.load_stats() 
            
            mode_name = "Front->Back" if self.play_mode_A_to_B else "Back->Front"
            self.stats_label.text = f"[color=00ff00]{mode_name} DATA CLEARED![/color]\n\n" + self.stats_label.text
            
            self.wipe_input.opacity = 0
            self.wipe_input.disabled = True
            self.btn_confirm_wipe.opacity = 0
            self.btn_confirm_wipe.disabled = True
            self.btn_init_wipe.text = "WIPED"
        else:
            self.wipe_input.text = ""
            self.wipe_input.hint_text = "Must type 'clear'!"

    def load_stats(self):
        counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for word_id in self.db:
            mode_data = self.get_mode_data(word_id)
            box = mode_data.get('box', 0)
            if box in counts: counts[box] += 1
            
        mode_str = "Front -> Back" if self.play_mode_A_to_B else "Back -> Front"
        self.stats_label.text = (
            f"[b]CURRENT MODE: {mode_str}[/b]\n"
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
        if not self.in_settings:
            self.label.text = "Scanning Files..."
        threading.Thread(target=self.load_data).start()

    def load_data(self):
        try:
            # 1. Load existing database
            if os.path.exists(self.db_path):
                try:
                    with open(self.db_path, 'r') as f:
                        self.db = json.load(f)
                        
                    # MIGRATION CHECK: Convert old DBs to new Unified format silently
                    for k, v in list(self.db.items()):
                        if 'box' in v:
                            self.db[k] = {
                                "a_to_b": {"box": v.get("box", 0), "due": v.get("due", 0)},
                                "b_to_a": {"box": 0, "due": 0},
                                "file_a": v.get("file_a", ""),
                                "file_b": v.get("file_b", "")
                            }
                except Exception as e: 
                    self.update_debug(f"DB Load Error: {e}")
                    self.db = {}
            else: self.db = {}

            # 2. Scan audio folder for new files
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
                            "a_to_b": {"box": 0, "due": 0},
                            "b_to_a": {"box": 0, "due": 0},
                            "file_a": os.path.join(self.audio_dir, f_a),
                            "file_b": os.path.join(self.audio_dir, file_b)
                        }
                        new_added += 1
                
                if new_added > 0: self.save_db()
                Clock.schedule_once(self.build_session_queue, 0)
                
                if self.in_settings:
                    Clock.schedule_once(lambda dt: self.load_stats(), 0)
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
            self.update_debug(f"Progress saved successfully.")
        except Exception as e:
            self.update_debug(f"SAVE BLOCKED: {str(e)}")

    @mainthread
    def build_session_queue(self, dt=None):
        now = time.time()
        due = [k for k in self.db if self.get_mode_data(k).get('due', 0) <= now and 0 < self.get_mode_data(k)['box'] < 5]
        due.sort(key=lambda k: (self.get_mode_data(k)['box'], self.get_mode_data(k)['due']))
        
        new_cards = [k for k in self.db if self.get_mode_data(k)['box'] == 0]
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

    # ================= ZERO-LAG AUDIO ENGINE =================
    def play_audio(self, filepath):
        if self.active_sound:
            try: self.active_sound.stop()
            except: pass
            
        # If it was preloaded, play it instantly!
        if filepath == self.preloaded_path and self.preloaded_sound:
            self.active_sound = self.preloaded_sound
        else:
            if os.path.exists(filepath):
                self.active_sound = SoundLoader.load(filepath)
                
        if self.active_sound: 
            self.active_sound.play()

    def preload_audio(self, filepath):
        """Silently loads the next track into memory while you listen"""
        if os.path.exists(filepath):
            self.preloaded_sound = SoundLoader.load(filepath)
            self.preloaded_path = filepath

    def get_text(self, filepath):
        name = os.path.basename(filepath)
        if "_A_" in name: return name.split("_A_")[-1].replace(".mp3", "").replace("_", " ")
        if "_B_" in name: return name.split("_B_")[-1].replace(".mp3", "").replace("_", " ")
        return name

    def refill_queue(self):
        if len(self.queue) >= SESSION_LIMIT:
            return

        now = time.time()
        active_ids = set(self.queue)
        if self.current_card: active_ids.add(self.current_card)
        
        due = [k for k in self.db if self.get_mode_data(k).get('due', 0) <= now and 0 < self.get_mode_data(k)['box'] < 5 and k not in active_ids]
        due.sort(key=lambda k: (self.get_mode_data(k)['box'], self.get_mode_data(k)['due']))
        
        if due:
            self.queue.append(due[0])
            return

        new_cards = [k for k in self.db if self.get_mode_data(k)['box'] == 0 and k not in active_ids]
        new_cards.sort()
        if new_cards:
            self.queue.append(new_cards[0])

    def get_current_play_files(self, data):
        if self.play_mode_A_to_B:
            return data['file_a'], data['file_b']
        else:
            return data['file_b'], data['file_a']

    def next_step(self):
        if not self.queue and not self.current_card: return

        if self.state == "IDLE" or self.state == "FINISHED_CARD":
            if self.current_card: self.history.append(self.current_card)
            
            self.current_card = self.queue.pop(0)
            self.state = "PLAYING_Q"
            data = self.db[self.current_card]
            mode_data = self.get_mode_data(self.current_card)
            
            q_file, a_file = self.get_current_play_files(data)
            
            self.label.text = f"[b]{self.get_text(q_file)}[/b]\n(Box {mode_data['box']})"
            self.label.color = (1, 1, 1, 1)
            
            self.play_audio(q_file)
            self.preload_audio(a_file) # Preload the answer!

        elif self.state == "PLAYING_Q":
            self.state = "PLAYING_A"
            data = self.db[self.current_card]
            q_file, a_file = self.get_current_play_files(data)
            
            self.label.text = f"[b]ANSWER[/b]\n{self.get_text(a_file)}"
            self.label.color = (1, 1, 0, 1)
            
            self.play_audio(a_file)
            
            # Preload the NEXT question in the queue!
            if self.queue:
                next_card_data = self.db[self.queue[0]]
                next_q_file, _ = self.get_current_play_files(next_card_data)
                self.preload_audio(next_q_file)

        elif self.state == "PLAYING_A":
            self.grade_card(success=False)

    def rewind_action(self):
        if self.active_sound: self.active_sound.stop()

        if self.state == "PLAYING_A":
            self.state = "PLAYING_Q"
            data = self.db[self.current_card]
            mode_data = self.get_mode_data(self.current_card)
            q_file, _ = self.get_current_play_files(data)
            
            self.label.text = f"[b]{self.get_text(q_file)}[/b]\n(Box {mode_data['box']})"
            self.label.color = (1, 1, 1, 1)
            self.play_audio(q_file)

        elif self.state == "PLAYING_Q" or self.state == "IDLE":
            if not self.history: return
            if self.current_card: self.queue.insert(0, self.current_card)
            self.current_card = self.history.pop()
            
            self.state = "PLAYING_Q"
            data = self.db[self.current_card]
            q_file, _ = self.get_current_play_files(data)
            
            self.label.text = f"<< REWINDING\n[b]{self.get_text(q_file)}[/b]"
            self.play_audio(q_file)

    def mark_as_known(self):
        if self.current_card:
            self.label.text = "[b]KNOWN[/b]"
            self.label.color = (0, 1, 0, 1)
            self.grade_card(success=True)

    def grade_card(self, success):
        if not self.current_card: return
        mode_data = self.get_mode_data(self.current_card)
        
        if success:
            mode_data['box'] += 1
            if mode_data['box'] >= len(INTERVALS): mode_data['box'] = len(INTERVALS) - 1
        else:
            mode_data['box'] = 0 
        
        wait_days = INTERVALS[mode_data['box']]
        if not success:
            mode_data['due'] = time.time()  # Instant database reset, no 300s lock
            self.queue.append(self.current_card) 
        else:
            mode_data['due'] = time.time() + (wait_days * 86400)

        threading.Thread(target=self.save_db).start()
        
        self.refill_queue()
        self.state = "FINISHED_CARD"
        self.next_step()

    def _on_keyboard_down(self, window, keycode, scancode, text, modifiers):
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
