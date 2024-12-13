import tank
import os
import sys

# Local storage path field for known Oses.
_OS_LOCAL_STORAGE_PATH_FIELD = {
    "darwin": "mac_path",
    "win32": "windows_path",
    "linux": "linux_path",
    "linux2": "linux_path",
}[sys.platform]

HookBaseClass = tank.get_hook_baseclass()

# Import unreal module only when in Unreal environment
try:
    import unreal
    UNREAL_AVAILABLE = True
except ImportError:
    UNREAL_AVAILABLE = False

class UnrealAssetPublishPlugin(HookBaseClass):
    """
    Plugin for publishing an Unreal asset.
    """

    @property
    def description(self):
        return """Publishes the asset to Shotgun. A <b>Publish</b> entry will be
        created in Shotgun which will include a reference to the exported asset's current
        path on disk. Other users will be able to access the published file via
        the <b>Loader</b> app so long as they have access to
        the file's location on disk."""

    @property
    def settings(self):
        base_settings = super(UnrealAssetPublishPlugin, self).settings or {}
        publish_template_setting = {
            "Publish Template": {
                "type": "template",
                "default": None,
                "description": "Template path for published work files. Should"
                               "correspond to a template defined in "
                               "templates.yml.",
            },
            "Publish Folder": {
                "type": "string",
                "default": None,
                "description": "Optional folder to use as a root for publishes"
            },
        }
        base_settings.update(publish_template_setting)
        return base_settings

    @property
    def item_filters(self):
        return ["unreal.asset.StaticMesh"]

    def accept(self, settings, item):
        """
        Method called by the publisher to determine if an item is of any interest to this plugin.
        Only items matching the filters defined via the item_filters property will be presented to this method.

        A publish task will be generated for each item accepted here.

        :param settings: Dictionary of Settings. The keys are strings, matching the keys returned in the settings property.
                       The values are `Setting` instances.
        :param item: Item to process

        :returns: dictionary with the following keys:
            - accepted (bool): True if the plugin should accept the item, False otherwise
            - enabled (bool): If True, the plugin will be enabled in the UI, otherwise it will be disabled.
                            Only applies to accepted tasks.
            - visible (bool): If True, the plugin will be visible in the UI, otherwise it will be hidden.
                            Only applies to accepted tasks.
            - checked (bool): If True, the plugin will be checked in the UI, otherwise it will be unchecked.
                            Only applies to accepted tasks.
        """
        if UNREAL_AVAILABLE and item.properties.get("unreal_asset_path"):
            return {"accepted": True}
        return {"accepted": False}

    def validate(self, settings, item):
        """
        Validates the given item to check that it is ok to publish.

        Returns a boolean to indicate validity.
        """
        publisher = self.parent
        engine = publisher.engine
        asset_path = item.properties.get("unreal_asset_path")

        if not UNREAL_AVAILABLE:
            error_msg = "Unreal is not available. Unable to export asset."
            self.logger.error(error_msg)
            raise Exception(error_msg)

        if not asset_path:
            error_msg = "Could not determine the asset path in Unreal."
            self.logger.error(error_msg)
            raise Exception(error_msg)

        return True

    def publish(self, settings, item):
        publisher = self.parent

        # Get the path in a normalized state. No trailing separator, separators are
        # appropriate for current os, no double separators, etc.
        path = sgtk.util.ShotgunPath.normalize(path)

        # Get the publish path
        publish_path = self._get_publish_path(settings, item)
        
        # Ensure the publish folder exists
        publish_folder = os.path.dirname(publish_path)
        self.parent.ensure_folder_exists(publish_folder)

        # Get the asset path and name
        asset_path = item.properties["unreal_asset_path"]
        asset_name = os.path.splitext(os.path.basename(publish_path))[0]

        # Export the asset to FBX
        _unreal_export_asset_to_fbx(publish_folder, asset_path, asset_name)

        # Register the publish
        self._register_publish(settings, item, publish_path)

        return True

def _unreal_export_asset_to_fbx(destination_path, asset_path, asset_name):
    """
    Export an asset to FBX from Unreal

    :param destination_path: The path where the exported FBX will be placed
    :param asset_path: The Unreal asset to export to FBX
    :param asset_name: The asset name to use for the FBX filename
    """
    task = _generate_fbx_export_task(destination_path, asset_path, asset_name)
    exported = unreal.Exporter.run_asset_export_task(task)
    if not exported:
        raise Exception("Failed to export asset to FBX")

def _generate_fbx_export_task(destination_path, asset_path, asset_name):
    """
    Create and configure an Unreal AssetExportTask

    :param destination_path: The path where the exported FBX will be placed
    :param asset_path: The Unreal asset to export to FBX
    :param asset_name: The FBX filename to export to
    :return the configured AssetExportTask
    """
    # Create the export task
    export_task = unreal.AssetExportTask()
    
    # Configure the task
    export_task.object = unreal.load_asset(asset_path)
    export_task.filename = os.path.join(destination_path, asset_name + ".fbx")
    export_task.selected = False
    export_task.replace_identical = True
    export_task.prompt = False
    export_task.automated = True
    
    return export_task
