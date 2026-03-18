import json
import os
from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.utils import platform
from kivy.clock import Clock

EXTERNAL_FOLDER_NAME = "DriveLearn"

class DriveLearnResetApp(App):
    def build(self):
        self.db = {}
        self.layout = BoxLayout(orientation='vertical', padding=40, spacing=20)
        
        self.title_label = Label(
            text="DriveLearn Utility", 
            font_size='28sp', 
            size_hint=(1, 0.2),
            bold=True
        )
        self.layout.add_widget(self.title_label)

        self.stats_label = Label(
            text="Loading stats...", 
            font_size='18sp', 
            halign="center",
            valign="middle",
            size_hint=(1, 0.5)
        )
        self.stats_label.bind(size=self.stats_label.setter('text_size'))
        self.layout.add_widget(self.stats_label)

        self.btn_reset = Button(
            text="WIPE PROGRESS",
            background_color=(0.8, 0, 0, 1),
            font_size='20sp',
            size_hint=(1, 0.3)
        )
        self.btn_reset.bind(on_press=self.execute_reset)
        self.layout.add_widget(self.btn_reset)

        if platform == 'android':
            from android.permissions import request_permissions, Permission
            def callback(permissions, results):
                self.load_stats()
            request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE], callback)
            self.db_path = os.path.join("/storage/emulated/0", EXTERNAL_FOLDER_NAME, 'progress.json')
        else:
            self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'progress.json')
            Clock.schedule_once(lambda dt: self.load_stats(), 0.5)

        return self.layout

    def load_stats(self):
        if not os.path.exists(self.db_path):
            self.stats_label.text = "No progress.json found.\nZero words tracked."
            return
            
        try:
            with open(self.db_path, 'r') as f:
                self.db = json.load(f)
                
            counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            for data in self.db.values():
                box = data.get('box', 0)
                if box in counts:
                    counts[box] += 1
            
            stats_text = (
                f"Total Words Tracked: {len(self.db)}\n\n"
                f"Box 0 (New/Fail): {counts[0]}\n"
                f"Box 1 (1 Day): {counts[1]}\n"
                f"Box 2 (4 Days): {counts[2]}\n"
                f"Box 3 (7 Days): {counts[3]}\n"
                f"Box 4 (30 Days): {counts[4]}\n"
                f"Box 5 (Mastered): {counts[5]}"
            )
            self.stats_label.text = stats_text
            
        except Exception as e:
            self.stats_label.text = f"Error reading file:\n{str(e)}"

    def execute_reset(self, instance):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
                self.stats_label.text = "PROGRESS DELETED.\nOpen DriveLearn to start fresh."
                self.stats_label.color = (0, 1, 0, 1)
                self.btn_reset.disabled = True
            except Exception as e:
                self.stats_label.text = f"ERROR:\n{str(e)}"
        else:
            self.stats_label.text = "No progress file found.\nAlready fresh."
            self.stats_label.color = (0, 1, 0, 1)

if __name__ == '__main__':
    DriveLearnResetApp().run()
