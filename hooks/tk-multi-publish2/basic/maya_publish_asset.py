import tank
import os
import sys
import maya.cmds as cmds
import maya.mel as mel

# 기본 publish 플러그인을 상속받기 위해 sgtk를 import
import sgtk

# 기본 publish 플러그인을 상속
HookBaseClass = sgtk.get_hook_baseclass()

class MayaAssetPublishPlugin(HookBaseClass):
    """
    Plugin for publishing a Maya asset.
    
    This hook relies on functionality found in the base file publisher hook in
    the publish2 app and should inherit from it in the configuration. The hook
    setting for this plugin should look something like this::

        hook: "{self}/publish_file.py:{engine}/tk-multi-publish2/basic/maya_publish_asset.py"
    """

    @property
    def description(self):
        return """Publishes the Maya asset to Shotgun. A <b>Publish</b> entry will be
        created in Shotgun which will include a reference to the exported asset's current
        path on disk. Other users will be able to access the published file via
        the <b>Loader</b> app so long as they have access to
        the file's location on disk."""

    @property
    def settings(self):
        base_settings = super(MayaAssetPublishPlugin, self).settings or {}
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
        return ["maya.session"]

    def accept(self, settings, item):
        if item.type == "maya.session":
            if not cmds.ls(type="mesh"):
                self.logger.warn("No meshes found in the scene")
                return {"accepted": False}
            return {"accepted": True}
        return {"accepted": False}

    def validate(self, settings, item):
        """
        Validates the given item to check that it is ok to publish.
        """
        publisher = self.parent
        path = _session_path()
        
        if not path:
            error_msg = "The Maya session has not been saved."
            self.logger.error(error_msg)
            raise Exception(error_msg)

        if not os.path.exists(path):
            error_msg = "The Maya session file '%s' does not exist." % path
            self.logger.error(error_msg)
            raise Exception(error_msg)

        # Get the publish path
        publish_path = self._get_publish_path(settings, item)
        
        # If the publish path exists, increment the version number
        if os.path.exists(publish_path):
            self.logger.info("A file already exists in the publish path. Looking for the next available version number.")
            publish_path = self._get_next_version_path(publish_path)
            
        # Store the publish path on the item properties
        item.properties["publish_path"] = publish_path

        return True

    def publish(self, settings, item):
        """
        Executes the publish logic for the given item and settings.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """
        publisher = self.parent

        # Ensure the session is saved
        _save_session()

        # Get the publish path from item properties (set during validate)
        publish_path = item.properties.get("publish_path")
        if not publish_path:
            error_msg = "Publish path not found in item properties."
            self.logger.error(error_msg)
            raise Exception(error_msg)
        
        # Ensure the publish folder exists
        publish_folder = os.path.dirname(publish_path)
        self.parent.ensure_folder_exists(publish_folder)
        
        try:
            # Export the FBX
            self._maya_export_fbx(publish_path)
            
            # Get context information safely
            step_name = publisher.context.step.get("name", "step") if publisher.context.step else "step"
            task_name = publisher.context.task.get("name", "task") if publisher.context.task else "task"

            # Get version number safely
            try:
                if hasattr(item.properties, "publish_version"):
                    version_number = item.properties.publish_version
                else:
                    # Try to extract version from publish_path
                    import re
                    version_pattern = re.compile(r"v(\d+)", re.IGNORECASE)
                    match = version_pattern.search(publish_path)
                    if match:
                        version_number = int(match.group(1))
                    else:
                        version_number = 1
            except:
                version_number = 1

            # Set the required properties on the item for base class to register
            item.properties.path = publish_path
            item.properties.publish_version = version_number
            item.properties.publish_name = "%s_%s_v%03d" % (task_name, step_name, version_number)
            item.properties.publish_type = "FBX File"
            
            # Let the base class register the publish
            super(MayaAssetPublishPlugin, self).publish(settings, item)
            
            self.logger.info("Publish completed successfully")
            return True
        except Exception as e:
            self.logger.error("Failed to publish: %s" % e)
            raise

    def _get_publish_path(self, settings, item):
        """
        Get the path where the plugin will publish the asset.
        """
        publisher = self.parent

        # Get the path in a normalized state
        path = _session_path()
        path = os.path.normpath(path)

        # Get settings values
        publish_template = settings.get("Publish Template")
        publish_template = publish_template.value if hasattr(publish_template, "value") else publish_template
        
        publish_folder = settings.get("Publish Folder")
        publish_folder = publish_folder.value if hasattr(publish_folder, "value") else publish_folder

        if publish_template:
            # Get fields from the current session path
            work_template = publisher.sgtk.template_from_path(path)
            fields = {}
            
            if work_template:
                fields = work_template.get_fields(path)
            
            # Add context fields
            step_name = publisher.context.step.get("name", "step") if publisher.context.step else "step"
            task_name = publisher.context.task.get("name", "task") if publisher.context.task else "task"
            fields["Step"] = step_name
            fields["name"] = task_name
            
            # Get the version number from the work file
            if "version" not in fields:
                fields["version"] = publisher.util.get_version_number(path)
            
            # Apply fields to publish template
            publish_template = publisher.sgtk.templates.get(publish_template)
            if not publish_template:
                raise Exception("Publish template '%s' not found!" % publish_template)
            
            missing_keys = publish_template.missing_keys(fields)
            if missing_keys:
                raise Exception("Missing required fields for publish template: %s" % missing_keys)
            
            return publish_template.apply_fields(fields)
        
        elif publish_folder:
            # Use publish folder with context-based filename
            basename = "%s.%s.v%03d" % (
                publisher.context.task.get("name", "task") if publisher.context.task else "task",
                publisher.context.step.get("name", "step") if publisher.context.step else "step",
                publisher.util.get_version_number(path)
            )
            publish_path = os.path.join(publish_folder, basename + ".fbx")
            return publish_path
        
        else:
            # Use the same path but with context-based filename
            directory = os.path.dirname(path)
            basename = "%s.%s.v%03d" % (
                publisher.context.task.get("name", "task") if publisher.context.task else "task",
                publisher.context.step.get("name", "step") if publisher.context.step else "step",
                publisher.util.get_version_number(path)
            )
            publish_path = os.path.join(directory, basename + ".fbx")
            return publish_path

    def _get_next_version_path(self, path):
        """
        Given a file path, return a new path with a version number incremented.
        """
        directory = os.path.dirname(path)
        filename = os.path.basename(path)
        basename, ext = os.path.splitext(filename)
        
        # Check if the basename ends with a version number
        import re
        version_pattern = re.compile(r"_v(\d+)$")
        match = version_pattern.search(basename)
        
        if match:
            # Get current version number and increment it
            current_version = int(match.group(1))
            new_version = current_version + 1
            # Replace the version number in the basename
            new_basename = version_pattern.sub("_v%03d" % new_version, basename)
        else:
            # No version number found, add v001
            new_basename = "%s_v001" % basename
            
        return os.path.join(directory, new_basename + ext)

    def _maya_export_fbx(self, publish_path):
        """FBX 내보내기 최적화 설정"""
        try:
            # Select all meshes
            all_meshes = cmds.ls(type="mesh", long=True)
            if not all_meshes:
                raise Exception("No meshes found in the scene")
            
            # Get the transform nodes of the meshes
            transform_nodes = [cmds.listRelatives(mesh, parent=True, fullPath=True)[0] for mesh in all_meshes]
            
            # Select the transform nodes
            cmds.select(transform_nodes, replace=True)
            
            # Reset FBX export options to default
            mel.eval('FBXResetExport')
            
            # FBX export settings
            mel.eval('FBXExportFileVersion "FBX202000"')  # 최신 FBX 버전 사용
            mel.eval('FBXExportUpAxis y')  # Y-up axis
            mel.eval('FBXExportShapes -v true')
            mel.eval('FBXExportSmoothingGroups -v true')
            mel.eval('FBXExportSmoothMesh -v true')
            mel.eval('FBXExportTangents -v true')  # 탄젠트 포함
            mel.eval('FBXExportInstances -v false')
            mel.eval('FBXExportReferencedAssetsContent -v false')
            mel.eval('FBXExportAnimationOnly -v false')
            mel.eval('FBXExportBakeComplexAnimation -v false')
            mel.eval('FBXExportConstraints -v false')
            mel.eval('FBXExportLights -v false')
            mel.eval('FBXExportCameras -v false')
            mel.eval('FBXExportEmbeddedTextures -v false')
            mel.eval('FBXExportInputConnections -v false')
            
            # Save the FBX
            mel.eval('FBXExport -f "%s" -s' % publish_path.replace("\\", "/"))
            
            self.logger.info("FBX exported successfully to: %s" % publish_path)
        except Exception as e:
            self.logger.error("Failed to export FBX: %s" % e)
            raise

def _session_path():
    """
    Return the path to the current session
    :return: str: The current session path
    """
    path = cmds.file(query=True, sn=True)

    if isinstance(path, bytes):
        path = path.decode('utf-8')
    elif path is None:
        path = ''

    return path

def _save_session():
    """
    Save the current session
    """
    try:
        cmds.file(save=True, force=True)
    except Exception as e:
        raise Exception("Failed to save session: %s" % e)
