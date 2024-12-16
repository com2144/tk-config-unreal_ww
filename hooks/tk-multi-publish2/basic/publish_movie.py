# This file is based on templates provided and copyrighted by Autodesk, Inc.
# This file has been modified by Epic Games, Inc. and is subject to the license
# file included in this repository.

import sgtk
import sys
from tank_vendor import six

import copy
import datetime
import os
import pprint
import subprocess
import tempfile

# Import unreal module only when in Unreal environment
try:
    import unreal
    UNREAL_AVAILABLE = True
except ImportError:
    UNREAL_AVAILABLE = False
    unreal = None

# Import maya module only when in Maya environment
try:
    import maya.cmds as cmds
    import maya.mel as mel
    MAYA_AVAILABLE = True
except ImportError:
    MAYA_AVAILABLE = False

# Get the engine name to determine the environment
ENGINE_NAME = os.environ.get("TANK_CURRENT_PC")

# Local storage path field for known Oses.
_OS_LOCAL_STORAGE_PATH_FIELD = {
    "darwin": "mac_path",
    "win32": "windows_path",
    "linux": "linux_path",
    "linux2": "linux_path",
}[sys.platform]

HookBaseClass = sgtk.get_hook_baseclass()


class UnrealMoviePublishPlugin(HookBaseClass):
    """
    Plugin for publishing an Unreal sequence as a rendered movie file.

    This hook relies on functionality found in the base file publisher hook in
    the publish2 app and should inherit from it in the configuration. The hook
    setting for this plugin should look something like this::

        hook: "{self}/publish_file.py:{engine}/tk-multi-publish2/basic/publish_session.py"

    To learn more about writing a publisher plugin, visit
    http://developer.shotgunsoftware.com/tk-multi-publish2/plugin.html
    """

    # NOTE: The plugin icon and name are defined by the base file plugin.

    @property
    def description(self):
        """
        Verbose, multi-line description of what the plugin does. This can
        contain simple html for formatting.
        """

        return """Publishes the sequence as a rendered movie to Shotgun. A
        <b>Publish</b> entry will be created in Shotgun which will include a
        reference to the movie's current path on disk. A <b>Version</b> entry
        will also be created in Shotgun with the movie file being uploaded
        there. Other users will be able to review the movie in the browser or
        in RV.
        <br>
        If available, the Movie Render Queue will be used for rendering,
        the Level Sequencer will be used otherwise.
        """

    @property
    def settings(self):
        """
        Dictionary defining the settings that this plugin expects to receive
        through the settings parameter in the accept, validate, publish and
        finalize methods.

        A dictionary on the following form::

            {
                "Settings Name": {
                    "type": "settings_type",
                    "default": "default_value",
                    "description": "One line description of the setting"
            }

        The type string should be one of the data types that toolkit accepts as
        part of its environment configuration.
        """

        # inherit the settings from the base publish plugin
        base_settings = super(UnrealMoviePublishPlugin, self).settings or {}

        # Here you can add any additional settings specific to this plugin
        publish_template_setting = {
            "Publish Template": {
                "type": "template",
                "default": None,
                "description": "Template path for published work files. Should"
                               "correspond to a template defined in "
                               "templates.yml.",
            },
            "Movie Render Queue Presets Path": {
                "type": "string",
                "default": None,
                "description": "Optional Unreal Path to saved presets "
                               "for rendering with the Movie Render Queue"
            },
            "Publish Folder": {
                "type": "string",
                "default": None,
                "description": "Optional folder to use as a root for publishes"
            }
        }

        # update the base settings
        base_settings.update(publish_template_setting)

        return base_settings

    @property
    def item_filters(self):
        """
        List of item types that this plugin is interested in.

        Only items matching entries in this list will be presented to the
        accept() method. Strings can contain glob patters such as *, for example
        ["maya.*", "file.maya"]
        """
        return ["unreal.asset.LevelSequence"]

    def create_settings_widget(self, parent):
        """
        Creates a Qt widget, for the supplied parent widget (a container widget
        on the right side of the publish UI).

        :param parent: The parent to use for the widget being created
        :return: A :class:`QtGui.QFrame` that displays editable widgets for
                 modifying the plugin's settings.
        """
        # defer Qt-related imports
        from sgtk.platform.qt import QtGui, QtCore

        # Create a QFrame with all our widgets
        settings_frame = QtGui.QFrame(parent)
        # Create our widgets, we add them as properties on the QFrame so we can
        # retrieve them easily. Qt uses camelCase so our xxxx_xxxx names can't
        # clash with existing Qt properties.

        # Show this plugin description
        settings_frame.description_label = QtGui.QLabel(self.description)
        settings_frame.description_label.setWordWrap(True)
        settings_frame.description_label.setOpenExternalLinks(True)
        settings_frame.description_label.setTextFormat(QtCore.Qt.RichText)

        # Unreal setttings
        settings_frame.unreal_render_presets_label = QtGui.QLabel("Render with Movie Pipeline Presets:")
        settings_frame.unreal_render_presets_widget = QtGui.QComboBox()
        settings_frame.unreal_render_presets_widget.addItem("No presets")
        if UNREAL_AVAILABLE:
            presets_folder = unreal.MovieRenderPipelineProjectSettings().preset_save_dir
            for preset in unreal.EditorAssetLibrary.list_assets(presets_folder.path):
                settings_frame.unreal_render_presets_widget.addItem(preset.split(".")[0])

        settings_frame.unreal_publish_folder_label = QtGui.QLabel("Publish folder:")
        storage_roots = self.parent.shotgun.find(
            "LocalStorage",
            [],
            ["code", _OS_LOCAL_STORAGE_PATH_FIELD]
        )
        settings_frame.storage_roots_widget = QtGui.QComboBox()
        settings_frame.storage_roots_widget.addItem("Current Unreal Project")
        for storage_root in storage_roots:
            if storage_root[_OS_LOCAL_STORAGE_PATH_FIELD]:
                settings_frame.storage_roots_widget.addItem(
                    "%s (%s)" % (
                        storage_root["code"],
                        storage_root[_OS_LOCAL_STORAGE_PATH_FIELD]
                    ),
                    userData=storage_root,
                )
        # Create the layout to use within the QFrame
        settings_layout = QtGui.QVBoxLayout()
        settings_layout.addWidget(settings_frame.description_label)
        settings_layout.addWidget(settings_frame.unreal_render_presets_label)
        settings_layout.addWidget(settings_frame.unreal_render_presets_widget)
        settings_layout.addWidget(settings_frame.unreal_publish_folder_label)
        settings_layout.addWidget(settings_frame.storage_roots_widget)

        settings_layout.addStretch()
        settings_frame.setLayout(settings_layout)
        return settings_frame

    def get_ui_settings(self, widget):
        """
        Method called by the publisher to retrieve setting values from the UI.

        :returns: A dictionary with setting values.
        """
        # defer Qt-related imports
        from sgtk.platform.qt import QtCore

        self.logger.info("Getting settings from UI")

        # Please note that we don't have to return all settings here, just the
        # settings which are editable in the UI.
        render_presets_path = None
        if widget.unreal_render_presets_widget.currentIndex() > 0:  # First entry is "No Presets"
            render_presets_path = six.ensure_str(widget.unreal_render_presets_widget.currentText())
        storage_index = widget.storage_roots_widget.currentIndex()
        publish_folder = None
        if storage_index > 0:  # Something selected and not the first entry
            storage = widget.storage_roots_widget.itemData(storage_index, role=QtCore.Qt.UserRole)
            publish_folder = storage[_OS_LOCAL_STORAGE_PATH_FIELD]

        settings = {
            "Movie Render Queue Presets Path": render_presets_path,
            "Publish Folder": publish_folder,
        }
        return settings

    def set_ui_settings(self, widget, settings):
        """
        Method called by the publisher to populate the UI with the setting values.

        :param widget: A QFrame we created in `create_settings_widget`.
        :param settings: A list of dictionaries.
        :raises NotImplementedError: if editing multiple items.
        """
        # defer Qt-related imports
        from sgtk.platform.qt import QtCore

        self.logger.info("Setting UI settings")
        if len(settings) > 1:
            # We do not allow editing multiple items
            raise NotImplementedError
        cur_settings = settings[0]
        render_presets_path = cur_settings["Movie Render Queue Presets Path"]
        preset_index = 0
        if render_presets_path:
            preset_index = widget.unreal_render_presets_widget.findText(render_presets_path)
            self.logger.info("Index for %s is %s" % (render_presets_path, preset_index))
        widget.unreal_render_presets_widget.setCurrentIndex(preset_index)
        # Note: the template is validated in the accept method, no need to check it here.
        publish_template_setting = cur_settings.get("Publish Template")
        publisher = self.parent
        publish_template = publisher.get_template_by_name(publish_template_setting)
        if isinstance(publish_template, sgtk.TemplatePath):
            widget.unreal_publish_folder_label.setEnabled(False)
            widget.storage_roots_widget.setEnabled(False)
        folder_index = 0
        publish_folder = cur_settings["Publish Folder"]
        if publish_folder:
            for i in range(widget.storage_roots_widget.count()):
                data = widget.storage_roots_widget.itemData(i, role=QtCore.Qt.UserRole)
                if data and data[_OS_LOCAL_STORAGE_PATH_FIELD] == publish_folder:
                    folder_index = i
                    break
            self.logger.debug("Index for %s is %s" % (publish_folder, folder_index))
        widget.storage_roots_widget.setCurrentIndex(folder_index)

    def load_saved_ui_settings(self, settings):
        """
        Load saved settings and update the given settings dictionary with them.

        :param settings: A dictionary where keys are settings names and
                         values Settings instances.
        """
        # Retrieve SG utils framework settings module and instantiate a manager
        fw = self.load_framework("tk-framework-shotgunutils_v5.x.x")
        module = fw.import_module("settings")
        settings_manager = module.UserSettings(self.parent)

        # Retrieve saved settings
        settings["Movie Render Queue Presets Path"].value = settings_manager.retrieve(
            "publish2.movie_render_queue_presets_path",
            settings["Movie Render Queue Presets Path"].value,
            settings_manager.SCOPE_PROJECT,
        )
        settings["Publish Folder"].value = settings_manager.retrieve(
            "publish2.publish_folder",
            settings["Publish Folder"].value,
            settings_manager.SCOPE_PROJECT
        )
        self.logger.debug("Loaded settings %s" % settings["Publish Folder"])
        self.logger.debug("Loaded settings %s" % settings["Movie Render Queue Presets Path"])

    def save_ui_settings(self, settings):
        """
        Save UI settings.

        :param settings: A dictionary of Settings instances.
        """
        # Retrieve SG utils framework settings module and instantiate a manager
        fw = self.load_framework("tk-framework-shotgunutils_v5.x.x")
        module = fw.import_module("settings")
        settings_manager = module.UserSettings(self.parent)

        # Save settings
        render_presets_path = settings["Movie Render Queue Presets Path"].value
        settings_manager.store("publish2.movie_render_queue_presets_path", render_presets_path, settings_manager.SCOPE_PROJECT)
        publish_folder = settings["Publish Folder"].value
        settings_manager.store("publish2.publish_folder", publish_folder, settings_manager.SCOPE_PROJECT)

    def accept(self, settings, item):
        """
        Method called by the publisher to determine if an item is of any
        interest to this plugin. Only items matching the filters defined via the
        item_filters property will be presented to this method.

        A publish task will be generated for each item accepted here. Returns a
        dictionary with the following booleans:

            - accepted: Indicates if the plugin is interested in this value at
                all. Required.
            - enabled: If True, the plugin will be enabled in the UI, otherwise
                it will be disabled. Optional, True by default.
            - visible: If True, the plugin will be visible in the UI, otherwise
                it will be hidden. Optional, True by default.
            - checked: If True, the plugin will be checked in the UI, otherwise
                it will be unchecked. Optional, True by default.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process

        :returns: dictionary with boolean keys accepted, required and enabled
        """

        accepted = True
        checked = True

        if ENGINE_NAME != "tk-unreal":
            self.logger.warning(
                "Movie publishing is not supported on other platforms than Unreal..."
            )
            return {
                "accepted": False,
            }

        publisher = self.parent
        # ensure the publish template is defined
        publish_template_setting = settings.get("Publish Template")
        publish_template = publisher.get_template_by_name(publish_template_setting.value)
        if not publish_template:
            self.logger.debug(
                "A publish template could not be determined for the "
                "item. Not accepting the item."
            )
            accepted = False

        # we've validated the work and publish templates. add them to the item properties
        # for use in subsequent methods
        item.properties["publish_template"] = publish_template
        self.load_saved_ui_settings(settings)
        return {
            "accepted": accepted,
            "checked": checked
        }

    def validate(self, settings, item):
        """
        Validates the given item to check that it is ok to publish.
        """
        if not super(UnrealMoviePublishPlugin, self).validate(settings, item):
            return False

        # Get the path in a normalized state
        path = sgtk.util.ShotgunPath.normalize(item.properties["path"])

        # Check the environment and validate accordingly
        if ENGINE_NAME == "tk-unreal":
            if not UNREAL_AVAILABLE:
                self.logger.error("Unreal engine not available")
                return False
            return self._validate_unreal(settings, item)
        elif ENGINE_NAME == "tk-maya":
            if not MAYA_AVAILABLE:
                self.logger.error("Maya environment not available")
                return False
            return self._validate_maya(settings, item)
        else:
            self.logger.error("Unsupported environment: %s" % ENGINE_NAME)
            return False

    def _validate_maya(self, settings, item):
        """
        Validate Maya specific settings and requirements
        """
        # Check that the camera exists
        if not cmds.ls(type="camera"):
            self.logger.error("No camera found in the scene")
            return False

        return True

    def publish(self, settings, item):
        """
        Executes the publish logic for the given item and settings.
        """
        publisher = self.parent

        # Get the path in a normalized state
        path = sgtk.util.ShotgunPath.normalize(item.properties["path"])

        # Determine which environment we're in and publish accordingly
        try:
            if ENGINE_NAME == "tk-unreal":
                if not UNREAL_AVAILABLE:
                    self.logger.error("Unreal engine not available")
                    return False
                self._publish_unreal(settings, item)
            elif ENGINE_NAME == "tk-maya":
                if not MAYA_AVAILABLE:
                    self.logger.error("Maya environment not available")
                    return False
                self._publish_maya(settings, item)
            else:
                self.logger.error("Unsupported environment: %s" % ENGINE_NAME)
                return False
        except Exception as e:
            self.logger.error("Failed to publish movie: %s" % str(e))
            return False

        # Let the base class register the publish
        super(UnrealMoviePublishPlugin, self).publish(settings, item)

    def _publish_maya(self, settings, item):
        """
        Publish and render movie from Maya
        """
        publish_path = item.properties["publish_path"]
        
        # Ensure the publish folder exists
        publish_folder = os.path.dirname(publish_path)
        self.parent.ensure_folder_exists(publish_folder)
        
        # Get the current camera
        active_panel = cmds.getPanel(withFocus=True)
        if cmds.getPanel(typeOf=active_panel) == "modelPanel":
            camera = cmds.modelPanel(active_panel, query=True, camera=True)
        else:
            # Get the first non-default camera
            all_cameras = cmds.ls(type="camera", long=True)
            non_default_cameras = [cam for cam in all_cameras 
                                 if not cmds.camera(cam, query=True, startupCamera=True)]
            if non_default_cameras:
                camera = non_default_cameras[0]
            else:
                camera = all_cameras[0]

        # Set playback range
        start_frame = cmds.playbackOptions(query=True, minTime=True)
        end_frame = cmds.playbackOptions(query=True, maxTime=True)

        # Store current viewport settings
        current_panel = cmds.getPanel(withFocus=True)
        original_settings = {}
        if cmds.getPanel(typeOf=current_panel) == "modelPanel":
            original_settings["displayAppearance"] = cmds.modelEditor(current_panel, query=True, displayAppearance=True)
            original_settings["displayTextures"] = cmds.modelEditor(current_panel, query=True, displayTextures=True)
            original_settings["displayLights"] = cmds.modelEditor(current_panel, query=True, displayLights=True)

            # Set viewport for high quality playblast
            cmds.modelEditor(current_panel, edit=True,
                           displayAppearance="smoothShaded",
                           displayTextures=True,
                           displayLights="all")

        try:
            # Playblast options
            playblast_options = {
                "filename": publish_path,
                "format": "qt",
                "compression": "H.264",
                "quality": 100,
                "width": 1920,
                "height": 1080,
                "percent": 100,
                "showOrnaments": False,
                "clearCache": True,
                "viewer": False,
                "startTime": start_frame,
                "endTime": end_frame,
                "camera": camera,
                "offScreen": True
            }

            # Create playblast
            temp_movie = cmds.playblast(**playblast_options)
            
            if os.path.exists(temp_movie):
                self.logger.info(
                    "Movie rendered successfully: %s" % publish_path
                )
                return True
            else:
                self.logger.error(
                    "Failed to render movie: %s" % publish_path
                )
                return False

        except Exception as e:
            self.logger.error("Failed to render movie: %s" % str(e))
            return False

        finally:
            # Restore viewport settings
            if cmds.getPanel(typeOf=current_panel) == "modelPanel":
                for setting, value in original_settings.items():
                    cmds.modelEditor(current_panel, edit=True, **{setting: value})

    def finalize(self, settings, item):
        """
        Execute the finalization pass. This pass executes once all the publish
        tasks have completed, and can for example be used to version up files.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """
        # do the base class finalization
        super(UnrealMoviePublishPlugin, self).finalize(settings, item)

    def _get_version_entity(self, item):
        """
        Returns the best entity to link the version to.
        """
        if item.context.entity:
            return item.context.entity
        elif item.context.project:
            return item.context.project
        else:
            return None

    def _unreal_asset_get_version(self, asset_path):
        if not UNREAL_AVAILABLE:
            return 0
        asset = unreal.EditorAssetLibrary.load_asset(asset_path)
        version_number = 0

        if not asset:
            return version_number

        engine = sgtk.platform.current_engine()
        tag = engine.get_metadata_tag("version_number")

        metadata = unreal.EditorAssetLibrary.get_metadata_tag(asset, tag)

        if not metadata:
            return version_number

        try:
            version_number = int(metadata)
        except ValueError:
            pass

        return version_number

    def _unreal_asset_set_version(self, asset_path, version_number):
        if not UNREAL_AVAILABLE:
            return
        asset = unreal.EditorAssetLibrary.load_asset(asset_path)

        if not asset:
            return

        engine = sgtk.platform.current_engine()
        tag = engine.get_metadata_tag("version_number")

        unreal.EditorAssetLibrary.set_metadata_tag(asset, tag, str(version_number))
        unreal.EditorAssetLibrary.save_loaded_asset(asset)

        # The save will pop up a progress bar that will bring the editor to the front thus hiding the publish app dialog
        # Workaround: Force all Shotgun dialogs to be brought to front
        engine = sgtk.platform.current_engine()
        for dialog in engine.created_qt_dialogs:
            dialog.raise_()

    def _check_render_settings(self, render_config):
        """
        Check settings from the given render preset and report which ones are problematic and why.

        :param render_config: An Unreal Movie Pipeline render config.
        :returns: A potentially empty list of tuples, where each tuple is a setting and a string explaining the problem.
        """
        invalid_settings = []
        # To avoid having multiple outputs, only keep the main render pass and the expected output format.
        for setting in render_config.get_all_settings():
            # Check for render passes. Since some classes derive from MoviePipelineDeferredPassBase, which is what we want to only keep
            # we can't use isinstance and use type instead.
            if isinstance(setting, unreal.MoviePipelineImagePassBase) and type(setting) != unreal.MoviePipelineDeferredPassBase:
                invalid_settings.append((setting, "Render pass %s would cause multiple outputs" % setting.get_name()))
            # Check rendering outputs
            elif isinstance(setting, unreal.MoviePipelineOutputBase) and not isinstance(setting, unreal.MoviePipelineAppleProResOutput):
                invalid_settings.append((setting, "Render output %s would cause multiple outputs" % setting.get_name()))
        return invalid_settings

    def _unreal_render_sequence_with_sequencer(self, output_path, unreal_map_path, sequence_path):
        """
        Renders a given sequence in a given level to a movie file with the Level Sequencer.

        :param str output_path: Full path to the movie to render.
        :param str unreal_map_path: Path of the Unreal map in which to run the sequence.
        :param str sequence_path: Content Browser path of sequence to render.
        :returns: True if a movie file was generated, False otherwise
                  string representing the path of the generated movie file
        """
        output_folder, output_file = os.path.split(output_path)
        movie_name = os.path.splitext(output_file)[0]

        # First, check if there's a file that will interfere with the output of the Sequencer
        # Sequencer can only render to avi or mov file format
        if os.path.isfile(output_path):
            # Must delete it first, otherwise the Sequencer will add a number in the filename
            try:
                os.remove(output_path)
            except OSError:
                self.logger.error(
                    "Couldn't delete {}. The Sequencer won't be able to output the movie to that file.".format(output_path)
                )
                return False, None

        # Render the sequence to a movie file using the following command-line arguments
        cmdline_args = [
            sys.executable,  # Unreal executable path
            "%s" % os.path.join(
                unreal.SystemLibrary.get_project_directory(),
                "%s.uproject" % unreal.SystemLibrary.get_game_name(),
            ),  # Unreal project
            unreal_map_path,  # Level to load for rendering the sequence
            # Command-line arguments for Sequencer Render to Movie
            # See: https://docs.unrealengine.com/en-us/Engine/Sequencer/Workflow/RenderingCmdLine
            #
            "-LevelSequence=%s" % sequence_path,  # The sequence to render
            "-MovieFolder=%s" % output_folder,  # Output folder, must match the work template
            "-MovieName=%s" % movie_name,  # Output filename
            "-game",
            "-MovieSceneCaptureType=/Script/MovieSceneCapture.AutomatedLevelSequenceCapture",
            "-ResX=1280",
            "-ResY=720",
            "-ForceRes",
            "-Windowed",
            "-MovieCinematicMode=yes",
            "-MovieFormat=Video",
            "-MovieFrameRate=24",
            "-MovieQuality=75",
            "-NoTextureStreaming",
            "-NoLoadingScreen",
            "-NoScreenMessages",
        ]

        if UNREAL_AVAILABLE:
            unreal.log(
                "Sequencer command-line arguments: {}".format(
                    " ".join(cmdline_args)
                )
            )

        # Make a shallow copy of the current environment and clear some variables
        run_env = copy.copy(os.environ)
        # Prevent SG TK to try to bootstrap in the new process
        if "UE_SHOTGUN_BOOTSTRAP" in run_env:
            del run_env["UE_SHOTGUN_BOOTSTRAP"]
        if "UE_SHOTGRID_BOOTSTRAP" in run_env:
            del run_env["UE_SHOTGRID_BOOTSTRAP"]

        subprocess.call(cmdline_args, env=run_env)

        return os.path.isfile(output_path), output_path

    def _unreal_render_sequence_with_movie_queue(self, output_path, unreal_map_path, sequence_path, presets=None, shot_name=None):
        """
        Renders a given sequence in a given level with the Movie Render queue.

        :param str output_path: Full path to the movie to render.
        :param str unreal_map_path: Path of the Unreal map in which to run the sequence.
        :param str sequence_path: Content Browser path of sequence to render.
        :param presets: Optional :class:`unreal.MoviePipelineMasterConfig` instance to use for renderig.
        :param str shot_name: Optional shot name to render a single shot from this sequence.
        :returns: True if a movie file was generated, False otherwise
                  string representing the path of the generated movie file
        :raises ValueError: If a shot name is specified but can't be found in
                            the sequence.
        """
        output_folder, output_file = os.path.split(output_path)
        movie_name = os.path.splitext(output_file)[0]

        qsub = unreal.MoviePipelineQueueEngineSubsystem()
        queue = qsub.get_queue()
        job = queue.allocate_new_job(unreal.MoviePipelineExecutorJob)
        job.sequence = unreal.SoftObjectPath(sequence_path)
        job.map = unreal.SoftObjectPath(unreal_map_path)
        # If a specific shot was given, disable all the others.
        if shot_name:
            shot_found = False
            for shot in job.shot_info:
                if shot.outer_name != shot_name:
                    self.logger.info("Disabling shot %s" % shot.outer_name)
                    shot.enabled = False
                else:
                    shot_found = True
            if not shot_found:
                raise ValueError(
                    "Unable to find shot %s in sequence %s, aborting..." % (shot_name, sequence_path)
                )
        # Set settings from presets, if any
        if presets:
            job.set_preset_origin(presets)
        # Ensure the settings we need are set.
        config = job.get_configuration()
        # https://docs.unrealengine.com/4.26/en-US/PythonAPI/class/MoviePipelineOutputSetting.html?highlight=setting#unreal.MoviePipelineOutputSetting
        output_setting = config.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
        output_setting.output_directory = unreal.DirectoryPath(output_folder)
        output_setting.output_resolution = unreal.IntPoint(1280, 720)
        output_setting.file_name_format = movie_name
        output_setting.override_existing_output = True  # Overwrite existing files
        # If needed we could enforce a frame rate, like for the Sequencer code.
        # output_setting.output_frame_rate = unreal.FrameRate(24)
        # output_setting.use_custom_frame_rate = True
        # Remove problematic settings
        for setting, reason in self._check_render_settings(config):
            self.logger.warning("Disabling %s: %s." % (setting.get_name(), reason))
            config.remove_setting(setting)

        # Default rendering
        config.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
        # Render to a movie
        config.find_or_add_setting_by_class(unreal.MoviePipelineAppleProResOutput)
        # TODO: check which codec we should use.

        # We render in a forked process that we can control.
        # It would be possible to render in from the running process using an
        # Executor, however it seems to sometimes deadlock if we don't let Unreal
        # process its internal events, rendering is asynchronous and being notified
        # when the render completed does not seem to be reliable.
        # Sample code:
        #    exc = unreal.MoviePipelinePIEExecutor()
        #    # If needed, we can store data in exc.user_data
        #    # In theory we can set a callback to be notified about completion
        #    def _on_movie_render_finished_cb(executor, result):
        #       print("Executor %s finished with %s" % (executor, result))
        #    # exc.on_executor_finished_delegate.add_callable(_on_movie_render_finished_cb)
        #    r = qsub.render_queue_with_executor_instance(exc)

        # We can't control the name of the manifest file, so we save and then rename the file.
        _, manifest_path = unreal.MoviePipelineEditorLibrary.save_queue_to_manifest_file(queue)

        manifest_path = os.path.abspath(manifest_path)
        manifest_dir, manifest_file = os.path.split(manifest_path)
        f, new_path = tempfile.mkstemp(
            suffix=os.path.splitext(manifest_file)[1],
            dir=manifest_dir
        )
        os.close(f)
        os.replace(manifest_path, new_path)

        self.logger.debug("Queue manifest saved in %s" % new_path)
        # We now need a path local to the unreal project "Saved" folder.
        manifest_path = new_path.replace(
            "%s%s" % (
                os.path.abspath(
                    os.path.join(unreal.SystemLibrary.get_project_directory(), "Saved")
                ),
                os.path.sep,
            ),
            "",
        )
        self.logger.debug("Manifest short path: %s" % manifest_path)
        # Command line parameters were retrieved by submitting a queue in Unreal Editor with
        # a MoviePipelineNewProcessExecutor executor.
        # https://docs.unrealengine.com/4.27/en-US/PythonAPI/class/MoviePipelineNewProcessExecutor.html?highlight=executor
        cmd_args = [
            sys.executable,
            "%s" % os.path.join(
                unreal.SystemLibrary.get_project_directory(),
                "%s.uproject" % unreal.SystemLibrary.get_game_name(),
            ),
            "MoviePipelineEntryMap?game=/Script/MovieRenderPipelineCore.MoviePipelineGameMode",
            "-game",
            "-Multiprocess",
            "-NoLoadingScreen",
            "-FixedSeed",
            "-log",
            "-Unattended",
            "-messaging",
            "-SessionName=\"Publish2 Movie Render\"",
            "-nohmd",
            "-windowed",
            "-ResX=1280",
            "-ResY=720",
            # TODO: check what these settings are
            "-dpcvars=%s" % ",".join([
                "sg.ViewDistanceQuality=4",
                "sg.AntiAliasingQuality=4",
                "sg.ShadowQuality=4",
                "sg.PostProcessQuality=4",
                "sg.TextureQuality=4",
                "sg.EffectsQuality=4",
                "sg.FoliageQuality=4",
                "sg.ShadingQuality=4",
                "r.TextureStreaming=0",
                "r.ForceLOD=0",
                "r.SkeletalMeshLODBias=-10",
                "r.ParticleLODBias=-10",
                "foliage.DitheredLOD=0",
                "foliage.ForceLOD=0",
                "r.Shadow.DistanceScale=10",
                "r.ShadowQuality=5",
                "r.Shadow.RadiusThreshold=0.001000",
                "r.ViewDistanceScale=50",
                "r.D3D12.GPUTimeout=0",
                "a.URO.Enable=0",
            ]),
            "-execcmds=r.HLOD 0",
            # This need to be a path relative the to the Unreal project "Saved" folder.
            "-MoviePipelineConfig=\"%s\"" % manifest_path,
        ]
        if UNREAL_AVAILABLE:
            unreal.log(
                "Movie Queue command-line arguments: {}".format(
                    " ".join(cmd_args)
                )
            )
        # Make a shallow copy of the current environment and clear some variables
        run_env = copy.copy(os.environ)
        # Prevent SG TK to try to bootstrap in the new process
        if "UE_SHOTGUN_BOOTSTRAP" in run_env:
            del run_env["UE_SHOTGUN_BOOTSTRAP"]
        if "UE_SHOTGRID_BOOTSTRAP" in run_env:
            del run_env["UE_SHOTGRID_BOOTSTRAP"]
        self.logger.info("Running %s" % cmd_args)
        subprocess.call(cmd_args, env=run_env)
        return os.path.isfile(output_path), output_path
