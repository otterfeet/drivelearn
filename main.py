import os
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.core.audio import SoundLoader
from kivy.clock import Clock
from kivy.utils import platform

# --- CONFIGURATION ---
# Folder names on your phone
EXTERNAL_FOLDER_NAME = "DriveLearn"
AUDIO_DIR_NAME = "audio_files"

class DriveLearnApp(App):
    def build(self):
        self.sound = None
        self.playlist = []
        self.current_index = 0
        self.is_playing = False

        # --- UI LAYOUT (Big Buttons for Running) ---
        self.layout = BoxLayout(orientation='vertical', padding=20, spacing=20)
        
        # 1. Title / Status Label
        self.status_label = Label(
            text="Initializing...", 
            font_size='24sp', 
            halign='center', 
            valign='middle',
            size_hint=(1, 0.4) 
        )
        self.status_label.bind(size=self.status_label.setter('text_size'))
        self.layout.add_widget(self.status_label)

        # 2. Controls Area
        controls = BoxLayout(orientation='horizontal', spacing=20, size_hint=(1, 0.3))
        
        # PREVIOUS Button
        self.btn_prev = Button(text="<<", font_size='40sp', background_color=(0.3, 0.3, 0.3, 1))
        self.btn_prev.bind(on_press=self.play_previous)
        controls.add_widget(self.btn_prev)

        # REPLAY / PLAY Button
        self.btn_play = Button(text="PLAY", font_size='30sp', background_color=(0, 0.8, 0, 1))
        self.btn_play.bind(on_press=self.toggle_play)
        controls.add_widget(self.btn_play)

        # NEXT Button
        self.btn_next = Button(text=">>", font_size='40sp', background_color=(0.3, 0.3, 0.3, 1))
        self.btn_next.bind(on_press=self.play_next)
        controls.add_widget(self.btn_next)

        self.layout.add_widget(controls)

        # 3. Setup Permissions & Files
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])
            self.app_path = os.path.join("/storage/emulated/0", EXTERNAL_FOLDER_NAME)
        else:
            self.app_path = os.path.dirname(os.path.abspath(__file__))

        Clock.schedule_once(self.load_playlist, 1)

        return self.layout

    def load_playlist(self, dt):
        audio_dir = os.path.join(self.app_path, AUDIO_DIR_NAME)
        
        if not os.path.exists(audio_dir):
            self.status_label.text = f"ERROR:\nCreate folder:\n{EXTERNAL_FOLDER_NAME}/{AUDIO_DIR_NAME}"
            self.status_label.color = (1, 0, 0, 1)
            return

        # Find files
        files = [f for f in os.listdir(audio_dir) if f.lower().endswith(('.mp3', '.wav', '.ogg'))]
        
        if not files:
            self.status_label.text = "No audio files found!"
            return

        files.sort()
        self.playlist = [os.path.join(audio_dir, f) for f in files]
        self.status_label.text = f"Ready: {len(self.playlist)} tracks.\nPress Start."
        self.btn_play.text = "START"

    def play_track(self, index):
        # Stop old sound
        if self.sound:
            self.sound.stop()
        
        # Loop index if it goes out of bounds
        if index < 0: index = len(self.playlist) - 1
        if index >= len(self.playlist): index = 0
        
        self.current_index = index
        filename = self.playlist[self.current_index]
        
        try:
            self.sound = SoundLoader.load(filename)
            if self.sound:
                # Bind the finish event to stop logic (NOT autoplay)
                self.sound.bind(on_stop=self.on_track_finished)
                self.sound.play()
                
                self.is_playing = True
                
                # Update Text
                short_name = os.path.basename(filename)
                self.status_label.text = f"Playing ({index+1}/{len(self.playlist)}):\n{short_name}"
                self.btn_play.text = "STOP"
                self.btn_play.background_color = (0.8, 0, 0, 1) # Red
            else:
                self.status_label.text = "Error loading file."
        except Exception as e:
            self.status_label.text = str(e)

    def toggle_play(self, instance):
        if not self.playlist: return

        if self.is_playing:
            # User hit STOP
            if self.sound: self.sound.stop()
            self.is_playing = False
            self.btn_play.text = "REPLAY"
            self.btn_play.background_color = (0, 0.8, 0, 1) # Green
        else:
            # User hit PLAY/REPLAY
            self.play_track(self.current_index)

    def play_next(self, instance):
        # User hit NEXT -> Play immediately
        self.play_track(self.current_index + 1)

    def play_previous(self, instance):
        # User hit PREV -> Play immediately
        self.play_track(self.current_index - 1)

    def on_track_finished(self, instance):
        # Track finished naturally. 
        # STOP and WAIT for user input.
        self.is_playing = False
        self.btn_play.text = "REPLAY"
        self.btn_play.background_color = (0, 0.8, 0, 1) # Green
        self.status_label.text += "\n(Finished)"

if __name__ == '__main__':
    DriveLearnApp().run()
