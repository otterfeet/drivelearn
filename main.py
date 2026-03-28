import json
import os
import time
import random
import threading
import sys
import traceback

from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.core.window import Window
from kivy.core.audio import SoundLoader
from kivy.clock import Clock, mainthread
from kivy.utils import platform

# ================= CRASH LOGGER =================
def write_crash_log(crash_text):
    try:
        log_path = "/storage/emulated/0/Download/DriveLearn_Crash.txt"
        with open(log_path, "a") as f:
            f.write("\n\n--- NEW LOG ---\n")
            f.write(crash_text)
    except:
        pass 

def global_exception_handler(exctype, value, tb):
    err = "".join(traceback.format_exception(exctype, value, tb))
    write_crash_log(f"GLOBAL EXCEPTION:\n{err}")
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = global_exception_handler

# ================= CONFIGURATION =================
EXTERNAL_FOLDER_NAME = "DriveLearn"
AUDIO_SUBFOLDER = "audio_files"

INTERVALS = [0, 1, 4, 7, 30, 36500] 
SESSION_LIMIT = 15
# =================================================

class DriveLearnApp(App):
    def build(self):
        try:
            self.state = "IDLE" 
            self.queue = []
            self.history = []
            self.current_card = None
            self.db = {}
            self.config = {}
            self.run_mode_active = False
            self.in_settings = False
            self.waiting_for_key = None
            
            self.active_sound = None
            self.preloaded_sound = None
            self.preloaded_path = ""
            self.wake_lock = None
            
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
            
            self.stats_label = Label(text="Loading stats...", font_size='16sp', halign="center", valign="middle", size_hint=(1, 0.25), markup=True)
            self.stats_label.bind(size=self.stats_label.setter('text_size'))
            self.settings_ui.add_widget(self.stats_label)

            self.toggles_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint=(1, 0.15))
            
            self.btn_toggle_mode = Button(text="MODE: Front -> Back", font_size='16sp', background_color=(0.5, 0.3, 0.8, 1))
            self.btn_toggle_mode.bind(on_press=self.toggle_play_mode)
            self.toggles_layout.add_widget(self.btn_toggle_mode)

            # Updated Toggle Button Text
            self.btn_toggle_media = Button(text="CAR/BACKGROUND: OFF", font_size='16sp', background_color=(0.8, 0.4, 0.2, 1))
            self.btn_toggle_media.bind(on_press=self.toggle_media_mode)
            self.toggles_layout.add_widget(self.btn_toggle_media)
            
            self.settings_ui.add_widget(self.toggles_layout)

            self.binds_layout = BoxLayout(orientation='horizontal', spacing=5, size_hint=(1, 0.15))
            self.btn_bind_next = Button(text="Map NEXT", background_color=(0.3, 0.3, 0.3, 1))
            self.btn_bind_next.bind(on_press=lambda x: self.start_binding("next", self.btn_bind_next))
            
            self.btn_bind_known = Button(text="Map KNOWN", background_color=(0.3, 0.3, 0.3, 1))
            self.btn_bind_known.bind(on_press=lambda x: self.start_binding("known", self.btn_bind_known))
            
            self.btn_bind_rewind = Button(text="Map REWIND", background_color=(0.3, 0.3, 0.3, 1))
            self.btn_bind_rewind.bind(on_press=lambda x: self.start_binding("rewind", self.btn_bind_rewind))
            
            self.btn_bind_reset = Button(text="RESET\nBINDS", background_color=(0.6, 0.2, 0.2, 1), size_hint=(0.5, 1))
            self.btn_bind_reset.bind(on_press=self.reset_binds)

            self.binds_layout.add_widget(self.btn_bind_next)
            self.binds_layout.add_widget(self.btn_bind_known)
            self.binds_layout.add_widget(self.btn_bind_rewind)
            self.binds_layout.add_widget(self.btn_bind_reset)
            self.settings_ui.add_widget(self.binds_layout)

            self.backup_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint=(1, 0.15))
            self.btn_export = Button(text="EXPORT BACKUP", background_color=(0.2, 0.6, 0.2, 1))
            self.btn_export.bind(on_press=self.show_export_menu)
            self.btn_import = Button(text="IMPORT BACKUP", background_color=(0.6, 0.4, 0.2, 1))
            self.btn_import.bind(on_press=self.show_import_menu)
            self.backup_layout.add_widget(self.btn_export)
            self.backup_layout.add_widget(self.btn_import)
            self.settings_ui.add_widget(self.backup_layout)

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
            self.config_path = os.path.join(self.app_dir, 'config.json')

            os.makedirs(self.app_dir, exist_ok=True)
            os.makedirs(self.audio_dir, exist_ok=True)

            self.load_user_config()

            if platform == 'android':
                self.request_storage_access()
            else:
                self.start_background_load()

            return self.root

        except Exception as e:
            err = traceback.format_exc()
            write_crash_log(f"FATAL BOOT CRASH:\n{err}")
            err_label = Label(text=f"FATAL BOOT CRASH:\n\n{err}", color=(1,0,0,1), text_size=(Window.width-40, None), halign="left", valign="top")
            err_label.bind(size=err_label.setter('text_size'))
            return err_label

    # ================= CONFIG & BACKGROUND LOGIC =================
    def on_start(self):
        try:
            if getattr(self, 'config', {}).get("media_mode", False):
                self.setup_media_session()
        except Exception as e: 
            write_crash_log(f"ON START MEDIA ERROR:\n{traceback.format_exc()}")

    def on_pause(self):
        return True

    def load_user_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    self.config = json.load(f)
            except:
                self.config = {"media_mode": False, "binds": {"next": [], "known": [], "rewind": []}}
        else:
            self.config = {"media_mode": False, "binds": {"next": [], "known": [], "rewind": []}}
            
        if "binds" not in self.config:
            self.config["binds"] = {"next": [], "known": [], "rewind": []}

        if self.config.get("media_mode", False):
            self.btn_toggle_media.text = "CAR/BACKGROUND: ON"
            self.btn_toggle_media.background_color = (0.2, 0.8, 0.2, 1)
        else:
            self.btn_toggle_media.text = "CAR/BACKGROUND: OFF"
            self.btn_toggle_media.background_color = (0.8, 0.4, 0.2, 1)

    def save_user_config(self):
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f)
        except Exception as e:
            self.update_debug(f"Config Save Error: {e}")

    def toggle_media_mode(self, instance=None):
        current_state = self.config.get("media_mode", False)
        self.config["media_mode"] = not current_state
        self.save_user_config()
        
        if self.config["media_mode"]:
            self.btn_toggle_media.text = "CAR/BACKGROUND: ON"
            self.btn_toggle_media.background_color = (0.2, 0.8, 0.2, 1)
            self.setup_media_session()
        else:
            self.btn_toggle_media.text = "CAR/BACKGROUND: OFF"
            self.btn_toggle_media.background_color = (0.8, 0.4, 0.2, 1)
            self.disable_media_session()

    def setup_media_session(self):
        if platform != 'android': return
        try:
            from jnius import autoclass
            Context = autoclass('android.content.Context')
            AudioManager = autoclass('android.media.AudioManager')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')

            # 1. Violently steal Audio Focus so the car stops talking to Spotify
            audio_manager = PythonActivity.mActivity.getSystemService(Context.AUDIO_SERVICE)
            audio_manager.requestAudioFocus(None, AudioManager.STREAM_MUSIC, AudioManager.AUDIOFOCUS_GAIN)

            # 2. Grab a Wake Lock so the CPU keeps accepting Bluetooth commands in the dark
            power_manager = PythonActivity.mActivity.getSystemService(Context.POWER_SERVICE)
            if not self.wake_lock:
                self.wake_lock = power_manager.newWakeLock(1, "DriveLearn:KeepAlive")
                self.wake_lock.acquire()
                
            self.update_debug("Audio Focus & WakeLock ON")
            
        except Exception as e:
            err = traceback.format_exc()
            write_crash_log(f"AUDIO FOCUS SETUP FAILED:\n{err}")
            self.update_debug("Audio Setup Failed! Check Crash Log.")

    def disable_media_session(self):
        if platform != 'android': return
        try:
            from jnius import autoclass
            Context = autoclass('android.content.Context')
            AudioManager = autoclass('android.media.AudioManager')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            
            # Abandon Audio Focus
            audio_manager = PythonActivity.mActivity.getSystemService(Context.AUDIO_SERVICE)
            audio_manager.abandonAudioFocus(None)

            # Release Wake Lock
            if self.wake_lock:
                try: self.wake_lock.release()
                except: pass
                self.wake_lock = None
                
            self.update_debug("Audio Focus & WakeLock OFF")
        except Exception as e:
            write_crash_log(f"AUDIO FOCUS DISABLE FAILED:\n{traceback.format_exc()}")

    # ================= KEY BINDING LOGIC =================
    def start_binding(self, action, button_widget):
        self.waiting_for_key = action
        self.btn_bind_next.text = "Map NEXT"
        self.btn_bind_known.text = "Map KNOWN"
        self.btn_bind_rewind.text = "Map REWIND"
        button_widget.text = "Press a key..."

    def reset_binds(self, instance):
        self.config["binds"] = {"next": [], "known": [], "rewind": []}
        self.save_user_config()
        self.stats_label.text = "[color=ffff00]Custom Keybinds Reset to Default![/color]\n\n" + self.stats_label.text

    # ================= UNIFIED DB HELPER =================
    def get_mode_data(self, card_id):
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
        self.waiting_for_key = None
        self.btn_bind_next.text = "Map NEXT"
        self.btn_bind_known.text = "Map KNOWN"
        self.btn_bind_rewind.text = "Map REWIND"
        
        self.root.clear_widgets()
        self.root.add_widget(self.main_ui)
        if self.queue:
            self.label.text = f"Queue: {len(self.queue)} Cards\n\n[Press Remote to Resume]"
            self.state = "IDLE"

    # ================= FILE BROWSER MENUS =================
    def show_import_menu(self, instance):
        content = BoxLayout(orientation='vertical')
        filechooser = FileChooserListView(path='/storage/emulated/0', filters=['*.json'])
        btn_layout = BoxLayout(size_hint_y=0.2)
        
        btn_cancel = Button(text="Cancel", background_color=(0.5, 0.5, 0.5, 1))
        btn_load = Button(text="Load File", background_color=(0.2, 0.6, 0.2, 1))
        
        btn_layout.add_widget(btn_cancel)
        btn_layout.add_widget(btn_load)
        content.add_widget(filechooser)
        content.add_widget(btn_layout)

        popup = Popup(title="Select Progress File to Import", content=content, size_hint=(0.95, 0.95))
        btn_cancel.bind(on_release=popup.dismiss)
        
        def _load(*args):
            if filechooser.selection:
                self.execute_import(filechooser.selection[0])
            popup.dismiss()
            
        btn_load.bind(on_release=_load)
        popup.open()

    def show_export_menu(self, instance):
        content = BoxLayout(orientation='vertical')
        filechooser = FileChooserListView(path='/storage/emulated/0', dirselect=True)
        btn_layout = BoxLayout(size_hint_y=0.2)
        
        btn_cancel = Button(text="Cancel", background_color=(0.5, 0.5, 0.5, 1))
        btn_save = Button(text="Save Here", background_color=(0.2, 0.6, 0.2, 1))
        
        btn_layout.add_widget(btn_cancel)
        btn_layout.add_widget(btn_save)
        content.add_widget(filechooser)
        content.add_widget(btn_layout)

        popup = Popup(title="Select Folder to Export Backup", content=content, size_hint=(0.95, 0.95))
        btn_cancel.bind(on_release=popup.dismiss)
        
        def _save(*args):
            target_path = filechooser.path
            if filechooser.selection and os.path.isdir(filechooser.selection[0]):
                target_path = filechooser.selection[0]
            self.execute_export(os.path.join(target_path, 'progress_backup.json'))
            popup.dismiss()
            
        btn_save.bind(on_release=_save)
        popup.open()

    def execute_export(self, target_path):
        try:
            with open(target_path, 'w') as f:
                json.dump(self.db, f)
            self.stats_label.text = f"[color=00ff00]Saved successfully to:\n{target_path}[/color]\n\n" + self.stats_label.text
        except Exception as e:
            self.stats_label.text = f"[color=ff0000]Export Failed: {e}[/color]\n\n" + self.stats_label.text

    def execute_import(self, source_path):
        if os.path.exists(source_path):
            try:
                with open(source_path, 'r') as f:
                    self.db = json.load(f)
                self.save_db()
                self.queue = []
                self.current_card = None
                self.state = "IDLE"
                Clock.schedule_once(self.build_session_queue, 0)
                self.load_stats()
                self.stats_label.text = f"[color=00ff00]Restored successfully from:\n{source_path}[/color]\n\n" + self.stats_label.text
            except Exception as e:
                self.stats_label.text = f"[color=ff0000]Import Failed: {e}[/color]\n\n" + self.stats_label.text

    # ================= WIPE LOGIC =================
    def show_wipe_confirm(self, instance):
        self.btn_init_wipe.text = "Type 'clear' ->"
        self.btn_init_wipe.disabled = True
        self.wipe_input.opacity = 1
        self.wipe_input.disabled = False
        self.btn_confirm_wipe.opacity = 1
        self.btn_confirm_wipe.disabled = False

    def execute_wipe(self, instance):
        if self.wipe_input.text.strip().lower() == 'clear':
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
                
                self.label.text = "[color=ffff00]ACTION REQUIRED:[/color]\n\nPlease toggle 'Allow'.\n\n[b]Then restart this app.[/b]"
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
            if os.path.exists(self.db_path):
                try:
                    with open(self.db_path, 'r') as f:
                        self.db = json.load(f)
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

            if os.path.exists(self.audio_dir):
                all_files = os.listdir(self.audio_dir)
                a_files = sorted([f for f in all_files if "_A_" in f and f.endswith(('.mp3', '.wav', '.ogg'))])
                
                new_added = 0
                for f_a in a_files:
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

    def play_audio(self, filepath):
        if self.active_sound:
            try: self.active_sound.stop()
            except: pass
            
        if filepath == self.preloaded_path and self.preloaded_sound:
            self.active_sound = self.preloaded_sound
        else:
            if os.path.exists(filepath):
                self.active_sound = SoundLoader.load(filepath)
                
        if self.active_sound: 
            self.active_sound.play()

    def preload_audio(self, filepath):
        if os.path.exists(filepath):
            self.preloaded_sound = SoundLoader.load(filepath)
            self.preloaded_path = filepath

    def get_text(self, filepath):
        name = os.path.basename(filepath)
        if "_A_" in name: return name.split("_A_")[-1].replace(".mp3", "").replace("_", " ")
        if "_B_" in name: return name.split("_B_")[-1].replace(".mp3", "").replace("_", " ")
        return name

    def refill_queue(self):
        if len(self.queue) >= SESSION_LIMIT: return

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
            self.preload_audio(a_file)

        elif self.state == "PLAYING_Q":
            self.state = "PLAYING_A"
            data = self.db[self.current_card]
            q_file, a_file = self.get_current_play_files(data)
            
            self.label.text = f"[b]ANSWER[/b]\n{self.get_text(a_file)}"
            self.label.color = (1, 1, 0, 1)
            
            self.play_audio(a_file)
            
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
            mode_data['due'] = time.time() 
            self.queue.append(self.current_card) 
        else:
            mode_data['due'] = time.time() + (wait_days * 86400)

        threading.Thread(target=self.save_db).start()
        
        self.refill_queue()
        self.state = "FINISHED_CARD"
        self.next_step()

    def _on_keyboard_down(self, window, keycode, scancode, text, modifiers):
        key_id = keycode[0] if isinstance(keycode, tuple) else keycode
        self.update_debug(f"Last Key: {key_id}")

        if self.waiting_for_key:
            action = self.waiting_for_key
            if key_id not in self.config["binds"][action]:
                self.config["binds"][action].append(key_id)
                self.save_user_config()
            
            self.waiting_for_key = None
            self.btn_bind_next.text = "Map NEXT"
            self.btn_bind_known.text = "Map KNOWN"
            self.btn_bind_rewind.text = "Map REWIND"
            self.stats_label.text = f"[color=00ff00]Mapped Key {key_id} to {action.upper()}![/color]\n\n" + self.stats_label.text
            return True

        if self.in_settings: return False

        next_keys = [273, 275, 24, 32, 13, 85, 266] + self.config["binds"].get("next", [])
        known_keys = [276, 25, 87, 269] + self.config["binds"].get("known", [])
        rewind_keys = [274, 88, 268] + self.config["binds"].get("rewind", [])

        if key_id in known_keys:
            self.mark_as_known()
            return True
        elif key_id in next_keys:
            self.next_step()
            return True
        elif key_id in rewind_keys:
            self.rewind_action()
            return True
            
        elif key_id == 27:
            if self.run_mode_active:
                self.toggle_run_mode()
                return True

        return False

if __name__ == '__main__':
    try:
        DriveLearnApp().run()
    except Exception as e:
        write_crash_log(f"__MAIN__ CRASH:\n{traceback.format_exc()}")
