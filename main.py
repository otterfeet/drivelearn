import os
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.core.audio import SoundLoader
from kivy.utils import platform
from kivy.clock import Clock

# --- CONFIGURATION ---
# This is the folder name you must create on your phone
EXTERNAL_FOLDER_NAME = "DriveLearn"

class DriveLearnApp(App):
    def build(self):
        self.layout = BoxLayout(orientation='vertical', padding=20, spacing=20)
        self.status_label = Label(text="Initializing...", font_size='20sp', halign='center')
        self.layout.add_widget(self.status_label)
        
        # 1. Check Permissions (Android Only)
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])
            self.app_path = os.path.join("/storage/emulated/0", EXTERNAL_FOLDER_NAME)
        else:
            # PC Mode (for testing)
            self.app_path = os.path.dirname(os.path.abspath(__file__))

        # 2. Check if Audio Files Exist
        Clock.schedule_once(self.check_files, 1)
        
        return self.layout

    def check_files(self, dt):
        audio_dir = os.path.join(self.app_path, 'audio_files')
        
        if not os.path.exists(audio_dir):
            self.status_label.text = (
                f"ERROR: Audio files not found!\n\n"
                f"1. Connect phone to PC.\n"
                f"2. Create folder: Internal Storage/{EXTERNAL_FOLDER_NAME}\n"
                f"3. Copy 'audio_files' folder inside it."
            )
            self.status_label.color = (1, 0, 0, 1) # Red text
        else:
            self.status_label.text = "Files Found!\nReady to Drive."
            self.status_label.color = (0, 1, 0, 1) # Green text
            self.setup_ui(audio_dir)

    def setup_ui(self, audio_dir):
        # Clear the status label
        self.layout.clear_widgets()
        
        # Example Button
        btn = Button(text="Play Test Sound", size_hint=(1, 0.2))
        btn.bind(on_press=lambda x: self.play_sound(audio_dir, "test.mp3")) # Replace 'test.mp3' with a real file name
        self.layout.add_widget(btn)

    def play_sound(self, directory, filename):
        file_path = os.path.join(directory, filename)
        sound = SoundLoader.load(file_path)
        if sound:
            sound.play()
        else:
            self.status_label.text = f"Could not load: {filename}"

if __name__ == '__main__':
    DriveLearnApp().run()
