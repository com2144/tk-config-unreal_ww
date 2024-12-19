import unreal
import os
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QPushButton, QLabel, QApplication, QFormLayout
from PySide6.QtCore import Qt

dialog = None

class FolderCreatorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Shot Folder Template")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Lable
        label = QLabel("Enter Episode, Sequence, Shot.")
        layout.addWidget(label)

        # Input
        form_layout = QFormLayout()
        self.episode_input = QLineEdit()
        self.sequence_input = QLineEdit()
        self.shot_input = QLineEdit()

        # Tab moveable setting
        self.episode_input.setFocusPolicy(Qt.StrongFocus)
        self.sequence_input.setFocusPolicy(Qt.StrongFocus)
        self.shot_input.setFocusPolicy(Qt.StrongFocus)

        # Add Form Layout
        form_layout.addRow("Episode:", self.episode_input)
        form_layout.addRow("Sequence:", self.sequence_input)
        form_layout.addRow("Shot:", self.shot_input)
        layout.addLayout(form_layout)

        # Create Button
        create_button = QPushButton("Create Folders")
        create_button.clicked.connect(self.create_folders)
        layout.addWidget(create_button)

        self.setLayout(layout)

    def create_folders(self):
        episode = self.episode_input.text().strip()
        sequence = self.sequence_input.text().strip()
        shot = self.shot_input.text().strip()

        if not (episode and sequence and shot):
            unreal.log_warning("Please enter all fields.")
            return

        # Current Project Path
        project_path = os.path.dirname(unreal.Paths.get_project_file_path())
        cinematics_path = os.path.join(project_path, "Content/Cinematics/LevelSequence")
        target_path = os.path.join(cinematics_path, episode, sequence, shot)

        # Unify path with slash (`/`)
        target_path = os.path.normpath(target_path).replace("\\", "/")

        # Create main path
        if not os.path.exists(target_path):
            os.makedirs(target_path)
            unreal.log(f"Folder created : {target_path}")

        # Create subpaths below the main path
        subfolders = [
            f"{episode}_{sequence}_{shot}_char",
            f"{episode}_{sequence}_{shot}_env",
            f"{episode}_{sequence}_{shot}_fx",
            f"{episode}_{sequence}_{shot}_prop",
            f"{episode}_{sequence}_{shot}_cam",
            f"{episode}_{sequence}_{shot}_lgt",
        ]

        for subfolder in subfolders:
            subfolder_path = os.path.normpath(os.path.join(target_path, subfolder)).replace("\\", "/")
            if not os.path.exists(subfolder_path):
                os.makedirs(subfolder_path)
                unreal.log(f"Folder created : {subfolder_path}")

        unreal.log("Successfully created all folders.")
        self.close()


def main():
    global dialog  # Manage as a global variable
    app = QApplication.instance()
    if not app:
        app = QApplication([])

    if dialog is None:  # Create only when dialog is not present
        dialog = FolderCreatorDialog()
    dialog.show()


if __name__ == "__main__":
    main()