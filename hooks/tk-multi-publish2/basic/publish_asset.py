# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import tank
import os
import sys
import datetime
from . import path_info
from . import context_fields

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

    def __init__(self, *args, **kwargs):
        super(UnrealAssetPublishPlugin, self).__init__(*args, **kwargs)
        self._path_info = self.load_framework("tk-framework-shotgunutils").import_module("path_info")
        self._context_fields = self.load_framework("tk-framework-shotgunutils").import_module("context_fields")

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
            "Additional Fields": {
                "type": "dict",
                "default": {},
                "description": "Additional fields to include in the publish template"
            }
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
        Validates the given item to check that it is ok to publish. Returns a
        boolean to indicate validity.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        :returns: True if item is valid, False otherwise.
        """
        publisher = self.parent
        
        # Get the publish template from the settings
        publish_template_name = settings.get("Publish Template").value
        publish_template = publisher.get_template_by_name(publish_template_name)
        if not publish_template:
            self.logger.error("No publish template found: %s" % publish_template_name)
            return False
            
        self.logger.debug("Using publish template: %s" % publish_template)
        
        # Get the context from the item or parent
        context = item.context or publisher.context
        if not context:
            self.logger.error("No context found for item: %s" % item)
            return False
            
        self.logger.debug("Validating with context: %s" % context)
        
        # Initialize fields dictionary
        fields = {}
        
        # Try to get fields from context first
        try:
            fields = context.as_template_fields(publish_template)
            self.logger.debug("Fields from context: %s" % fields)
        except Exception as e:
            self.logger.debug("Unable to get fields from context: %s" % e)
        
        # Get fields from entity
        if context.entity:
            self.logger.debug("Entity fields: %s" % context.entity)
            if not isinstance(context.entity, dict):
                self.logger.error("Context entity is not a dictionary")
                return False
                
            fields["Asset"] = context.entity.get("code")
            fields["sg_asset_type"] = context.entity.get("sg_asset_type")
            
            if not fields.get("Asset") or not fields.get("sg_asset_type"):
                self.logger.error("Missing required entity fields. Asset: %s, sg_asset_type: %s" % 
                                (fields.get("Asset"), fields.get("sg_asset_type")))
                return False
        else:
            self.logger.error("Context has no entity")
            return False
            
        # Get fields from step
        if context.step:
            self.logger.debug("Step fields: %s" % context.step)
            if not isinstance(context.step, dict):
                self.logger.error("Context step is not a dictionary")
                return False
                
            fields["Step"] = context.step.get("short_name")
            if not fields.get("Step"):
                self.logger.error("Missing required step field: short_name")
                return False
        else:
            self.logger.error("Context has no step")
            return False
            
        # Get version from path or default to 1
        path = item.properties.get("path")
        version = 1
        if path:
            import re
            version_pattern = re.compile(r"\.?v(\d+)", re.IGNORECASE)
            match = version_pattern.search(path)
            if match:
                version = int(match.group(1))
        fields["version"] = version
        
        # Get name from item properties
        fields["name"] = item.properties.get("asset_name", "unknown")
        
        # Add date fields
        import datetime
        current_time = datetime.datetime.now()
        fields.update({
            "YYYY": current_time.year,
            "MM": current_time.month,
            "DD": current_time.day
        })
        
        self.logger.debug("Final fields: %s" % fields)
        
        # Validate against template
        missing_keys = publish_template.missing_keys(fields)
        if missing_keys:
            self.logger.error("Missing required fields for template: %s" % missing_keys)
            self.logger.error("Current fields: %s" % fields)
            return False
            
        # Try to create the publish path
        try:
            publish_path = publish_template.apply_fields(fields)
            item.properties["publish_path"] = publish_path
            item.properties["fields"] = fields
            self.logger.debug("Publish path: %s" % publish_path)
            return True
        except Exception as e:
            self.logger.error("Error creating publish path: %s" % e)
            return False

    def publish(self, settings, item):
        """
        Executes the publish logic for the given item and settings.
        """
        publisher = self.parent

        # Get the publish path
        publish_path = item.properties["publish_path"]
        
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
        raise Exception("FBX 내보내기에 실패했습니다.")

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
