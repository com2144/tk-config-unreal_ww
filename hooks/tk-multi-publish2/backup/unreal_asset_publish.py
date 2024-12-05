# This file is based on templates provided and copyrighted by Autodesk, Inc.
# This file has been modified by Epic Games, Inc. and is subject to the license
# file included in this repository.

import sgtk
import os
import sys
import unreal
import datetime

# Local storage path field for known Oses.
_OS_LOCAL_STORAGE_PATH_FIELD = {
    "darwin": "mac_path",
    "win32": "windows_path",
    "linux": "linux_path",
    "linux2": "linux_path",
}[sys.platform]

HookBaseClass = sgtk.get_hook_baseclass()

class UnrealAssetPublishPlugin(HookBaseClass):
    """
    Plugin for publishing an Unreal asset.

    This hook relies on functionality found in the base file publisher hook in
    the publish2 app and should inherit from it in the configuration. The hook
    setting for this plugin should look something like this::

        hook: "{self}/publish_file.py:{config}/tk-multi-publish2/unreal_asset_publish.py"
    """

    @property
    def description(self):
        """
        Verbose, multi-line description of what the plugin does.
        """
        return """Publishes the asset to Shotgun. A <b>Publish</b> entry will be
        created in Shotgun which will include a reference to the exported asset's current
        path on disk. Other users will be able to access the published file via
        the <b>Loader</b> app so long as they have access to
        the file's location on disk."""

    @property
    def settings(self):
        """
        Dictionary defining the settings that this plugin expects to receive
        through the settings parameter in the accept, validate, publish and
        finalize methods.
        """
        # inherit the settings from the base publish plugin
        base_settings = super(UnrealAssetPublishPlugin, self).settings or {}

        # Here you can add any additional settings specific to this plugin
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

        # update the base settings
        base_settings.update(publish_template_setting)

        return base_settings

    @property
    def item_filters(self):
        """
        List of item types that this plugin is interested in.
        """
        return ["unreal.asset.StaticMesh"]

    def accept(self, settings, item):
        """
        Method called by the publisher to determine if an item is of any interest to this plugin.
        Only items matching the filters defined via the item_filters property will be presented to this method.
        
        A publish task will be generated for each item accepted here. Returns a dictionary with the following booleans:
            accepted: Indicates if the plugin is interested in this value at all. Required.
            enabled: If True, the plugin will be enabled in the UI, otherwise it will be disabled. Optional, True by default.
            visible: If True, the plugin will be visible in the UI, otherwise it will be hidden. Optional, True by default.
            checked: If True, the plugin will be checked in the UI, otherwise it will be unchecked. Optional, True by default.
        """
        
        # Get the path in a normalized state
        asset_path = item.properties.get("asset_path")
        asset_name = item.properties.get("asset_name")
        
        if not asset_path or not asset_name:
            self.logger.warn("Asset path or name not found for item")
            return {"accepted": False}
            
        # Set the path on the item properties - this is needed by the base plugin
        item.properties["path"] = asset_path
        
        # Get publish template from settings
        publish_template = self.get_publish_template(settings, item)
        if publish_template:
            item.properties["publish_template"] = publish_template
        
        return {
            "accepted": True,
            "checked": True
        }

    def get_publish_template(self, settings, item):
        """
        Get the publish template from the settings.
        """
        # Get the template from the settings
        publish_template = settings.get("Publish Template").value
        if not publish_template:
            self.logger.debug(
                "No publish template defined for item: %s" % item.name
            )
            return None

        return self.parent.engine.get_template_by_name(publish_template)

    def validate(self, settings, item):
        """
        Validates the given item to check that it is ok to publish.
        """
        asset_path = item.properties.get("asset_path")
        asset_name = item.properties.get("asset_name")
        if not asset_path or not asset_name:
            self.logger.debug("Asset path or name not configured.")
            return False

        publish_template = item.properties["publish_template"]

        # Add the Unreal asset name to the fields
        fields = {"name": asset_name}

        # Get the current context from ShotGrid
        context = item.context
        
        # Get entity from context
        if context.entity is None:
            self.logger.warning(
                "Context has no entity! Please select a task or link this file to an asset.",
                extra={
                    "action_button": {
                        "label": "Review Context",
                        "tooltip": "Open context in ShotGrid",
                        "callback": lambda: self.parent.engine.show_panel("tk-multi-shotgunpanel")
                    }
                }
            )
            return False

        # Add required template fields from context
        fields["Asset"] = context.entity["name"]
        
        # Safely get asset type
        asset_type = context.entity.get("sg_asset_type")
        if not asset_type:
            # Try to get type from entity type
            asset_type = context.entity.get("type", "Asset")
            self.logger.warning(
                "Asset type not found in ShotGrid. Using default type: %s" % asset_type,
                extra={
                    "action_button": {
                        "label": "Configure Asset",
                        "tooltip": "Set asset type in ShotGrid",
                        "callback": lambda: self.parent.engine.show_panel("tk-multi-shotgunpanel")
                    }
                }
            )
        
        fields["sg_asset_type"] = asset_type
        
        # Get step from context
        if context.step is None:
            self.logger.warning(
                "Context has no step! Please select a task with a pipeline step.",
                extra={
                    "action_button": {
                        "label": "Review Task",
                        "tooltip": "Open task in ShotGrid",
                        "callback": lambda: self.parent.engine.show_panel("tk-multi-shotgunpanel")
                    }
                }
            )
            return False
            
        fields["Step"] = context.step["name"]
        
        # Add today's date to the fields
        date = datetime.date.today()
        fields["YYYY"] = date.year
        fields["MM"] = date.month
        fields["DD"] = date.day

        # Get next version number
        fields["version"] = self._get_next_version(publish_template, fields)
        
        # Get destination path for exported FBX from publish template
        try:
            publish_path = publish_template.apply_fields(fields)
        except Exception as e:
            self.logger.warning(
                f"Failed to apply fields to publish template: {str(e)}",
                extra={
                    "action_button": {
                        "label": "Review Template",
                        "tooltip": "Check template configuration",
                        "callback": lambda: self.parent.engine.show_panel("tk-multi-shotgunpanel")
                    }
                }
            )
            return False

        publish_path = os.path.normpath(publish_path)
        if not os.path.isabs(publish_path):
            # If the path is not absolute, prepend the publish folder setting.
            publish_folder = settings["Publish Folder"].value
            if not publish_folder:
                publish_folder = unreal.Paths.project_saved_dir()
            publish_path = os.path.abspath(
                os.path.join(
                    publish_folder,
                    publish_path
                )
            )
            
        # Log the fields and paths for debugging
        self.logger.debug(f"Template fields: {fields}")
        self.logger.debug(f"Publish path: {publish_path}")
            
        item.properties["publish_path"] = publish_path
        item.properties["path"] = publish_path

        # Remove the filename from the publish path
        destination_path = os.path.dirname(publish_path)

        # Stash the destination path in properties
        item.properties["destination_path"] = destination_path

        # Set the Published File Type
        item.properties["publish_type"] = "Unreal FBX"

        return True
        
    def _get_next_version(self, template, fields):
        """
        Find the next available version number
        
        :param template: Template to use for version calculation
        :param fields: Fields to use for template
        :return: Next version number
        """
        # Start with version 1
        version = 1
        
        # Get all existing versions
        try:
            existing_versions = self.parent.engine.tank.paths_from_template(
                template,
                fields,
                skip_keys=["version"]
            )
            
            # Find highest version
            for existing_version in existing_versions:
                cur_fields = template.get_fields(existing_version)
                cur_version = cur_fields.get("version", 0)
                if cur_version > version:
                    version = cur_version
                    
            # Increment for next version
            version += 1
            
        except Exception as e:
            self.logger.debug(f"Error finding next version: {str(e)}")
            # Return version 1 if there's any error
            return 1
            
        return version

    def publish(self, settings, item):
        """
        Executes the publish logic for the given item and settings.
        """
        # get the path in a normalized state. no trailing separator, separators
        # are appropriate for current os, no double separators, etc.
        destination_path = item.properties["destination_path"]
        asset_path = item.properties["asset_path"]
        asset_name = item.properties["asset_name"]

        # Ensure the destination path exists
        self._ensure_destination_path_exists(destination_path)

        # Export the asset to FBX
        self._unreal_export_asset_to_fbx(destination_path, asset_path, asset_name)

        # Let the base class register the publish
        super(UnrealAssetPublishPlugin, self).publish(settings, item)

    def _ensure_destination_path_exists(self, destination_path):
        """
        Ensures the destination path exists by creating it if it doesn't.
        """
        if not os.path.exists(destination_path):
            os.makedirs(destination_path)

    def _unreal_export_asset_to_fbx(self, destination_path, asset_path, asset_name):
        """
        Export the asset to FBX using Unreal's export functionality.
        
        :param destination_path: The directory where the FBX will be saved
        :param asset_path: The Unreal asset path
        :param asset_name: The name of the asset
        """
        # Ensure the asset exists
        asset = unreal.load_asset(asset_path)
        if not asset:
            self.logger.error(f"Failed to load asset: {asset_path}")
            return False
            
        # Create the full export path, ensuring it uses forward slashes
        export_path = os.path.normpath(destination_path).replace("\\", "/")
        
        # Ensure the destination directory exists
        os.makedirs(os.path.dirname(export_path), exist_ok=True)
        
        # Get the asset tools
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        
        try:
            # Get the clean asset path (remove /Game/ prefix if present)
            clean_asset_path = asset_path.replace("/Game/", "")
            if clean_asset_path.startswith("/"):
                clean_asset_path = clean_asset_path[1:]
                
            self.logger.debug(f"Exporting asset from: {clean_asset_path}")
            self.logger.debug(f"Exporting to: {export_path}")
            
            # Export the asset
            exported = asset_tools.export_assets(
                [clean_asset_path],  # 에셋 경로 목록
                export_path          # 내보내기 경로
            )
            
            if not exported:
                self.logger.error(f"Failed to export asset to: {export_path}")
                return False
                
            self.logger.info(f"Successfully exported asset to: {export_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exporting asset: {str(e)}")
            return False

    def _generate_fbx_export_task(self, destination_path, asset_path, asset_name):
        """
        Generate an FBX export task for the given asset.
        """
        export_task = unreal.AssetExportTask()
        export_task.object = unreal.load_asset(asset_path)
        export_task.filename = os.path.join(destination_path, f"{asset_name}.fbx")
        export_task.selected = False
        export_task.replace_identical = True
        export_task.prompt = False
        export_task.automated = True
        
        return export_task
