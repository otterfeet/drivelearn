import os
from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.utils import platform

EXTERNAL_FOLDER_NAME = "DriveLearn"

class DriveLearnResetApp(App):
    def build(self):
        self.layout = BoxLayout(orientation='vertical', padding=40, spacing=20)
        
        self.label = Label(
            text="DriveLearn Reset Utility\n\nWarning: This will wipe all progress.", 
            font_size='24sp', 
            halign="center",
            color=(1, 0, 0, 1)
        )
        self.layout.add_widget(self.label)

        self.btn_reset = Button(
            text="DELETE PROGRESS.JSON",
            background_color=(0.8, 0, 0, 1),
            font_size='20sp',
            size_hint=(1, 0.4)
        )
        self.btn_reset.bind(on_press=self.execute_reset)
        self.layout.add_widget(self.btn_reset)

        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])
            self.db_path = os.path.join("/storage/emulated/0", EXTERNAL_FOLDER_NAME, 'progress.json')
        else:
            self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'progress.json')

        return self.layout

    def execute_reset(self, instance):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
                self.label.text = "SUCCESS.\n\nprogress.json has been deleted.\nOpen DriveLearn to start fresh."
                self.label.color = (0, 1, 0, 1)
                self.btn_reset.disabled = True
            except Exception as e:
                self.label.text = f"ERROR:\n{str(e)}"
        else:
            self.label.text = "No progress file found.\nYou are already starting fresh."
            self.label.color = (0, 1, 0, 1)

if __name__ == '__main__':
    DriveLearnResetApp().run()