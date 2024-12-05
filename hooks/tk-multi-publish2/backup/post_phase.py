# Copyright (c) 2022 Autodesk, Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.

import copy
import os
import tempfile
import uuid

import sgtk
from tank_vendor import yaml

HookBaseClass = sgtk.get_hook_baseclass()


class PostPhase(HookBaseClass):
    """
    퍼블리시 단계 이후에 실행되는 후처리 훅입니다.
    각 퍼블리시 단계(검증, 퍼블리시, 마무리)가 완료된 후 실행되는 메서드들을 정의합니다.

    작동 원리:
    1. 퍼블리시 트리를 통해 모든 퍼블리시된 아이템에 접근
    2. 각 아이템의 상태를 검사하고 필요한 후처리 작업 수행
    3. 퍼블리시 결과에 따른 추가 작업 실행 (예: 알림, 로그 기록 등)
    """

    """
    퍼블리시의 각 단계 이후에 실행되는 메서드들을 정의하는 훅 클래스입니다.
    
    주요 기능:
    - 검증 단계 이후 처리 (post_validate)
    - 퍼블리시 단계 이후 처리 (post_publish)
    - 마무리 단계 이후 처리 (post_finalize)
    
    각 메서드는 PublishTree 인스턴스를 받아 퍼블리시된 아이템들을 처리할 수 있습니다.
    """

    def post_publish(self, publish_tree):
        """
        퍼블리시 단계가 완료된 후, 마무리 단계 전에 실행되는 메서드입니다.
        
        작동 과정:
        1. 퍼블리시 트리의 모든 아이템을 순회
        2. 각 아이템의 properties를 검사하여 퍼블리시 상태 확인
        3. 필요한 후처리 작업 수행
        
        참고: local_properties는 퍼블리시 플러그인 실행 중에만 접근 가능합니다.
        """
        
        # Iterate through all items in the publish tree
        for item in publish_tree:
            if item.type == "maya.fbx.unreal":
                self._export_maya_fbx(item)

        # ------------------------------------------------------------------------
        # Manage background publishing process
        # ------------------------------------------------------------------------

        monitor_data = {
            "items": [],
            "session_name": publish_tree.root_item.properties.get("session_name", ""),
        }

        current_engine = sgtk.platform.current_engine()
        bg_publish_app = current_engine.apps.get("tk-multi-bg-publish")

        bg_processing = publish_tree.root_item.properties.get("bg_processing")
        in_bg_process = publish_tree.root_item.properties.get("in_bg_process")

        # we only want to run the actions if we're going to publish in background but we're not already in the
        # background publishing process
        if not bg_processing or in_bg_process:
            return

        # modify the publish tree in order to add a new property/setting on the fly in order to give
        # the item/task a unique identifier
        # this will be very useful to track the tasks progress on the monitor side
        # we can't rely on names here as some items/tasks can have the same name
        # at the same time, start to build the monitor tree
        for item in publish_tree:

            # if the item has a thumbnail, download it and make sure we can access it later in the bg process
            thumbnail_path = item.get_thumbnail_as_path()
            if thumbnail_path:
                item._thumbnail_path = thumbnail_path

            item_uuid = str(uuid.uuid4())
            item_data = {
                "name": item.name,
                "uuid": item_uuid,
                "status": bg_publish_app.constants.WAITING_TO_START,
                "tasks": [],
                "is_parent_root": item.parent.is_root,
            }

            for task in item.tasks:
                if task.active:

                    # as we can't create a PublishSetting object using the Publish API, convert the task to a dict then
                    # add the new setting to finally reset the task from the dict
                    uuid_setting = {
                        "name": "Task UUID",
                        "type": "str",
                        "default_value": None,
                        "description": "UUID of the current task",
                        "value": str(uuid.uuid4()),
                    }
                    dummy_task_dict = task.to_dict()
                    dummy_task_dict["settings"]["Task UUID"] = uuid_setting
                    dummy_task = task.from_dict(dummy_task_dict, None)
                    task.settings["Task UUID"] = dummy_task.settings["Task UUID"]

                    item_data["tasks"].append(
                        {
                            "name": task.name,
                            "uuid": uuid_setting["value"],
                            "status": bg_publish_app.constants.WAITING_TO_START,
                        }
                    )

            if item_data["tasks"]:
                item.properties.uuid = item_uuid
                monitor_data["items"].append(item_data)

        # get the path to the folder where all the files used by the background publishing process will be stored
        root_folder_path = os.path.join(
            bg_publish_app.cache_location, current_engine.name
        )
        if not os.path.exists(root_folder_path):
            os.makedirs(root_folder_path)
        tmp_folder_path = tempfile.mkdtemp(dir=root_folder_path)

        # build the path to these files
        self.__TREE_FILE_PATH = os.path.join(tmp_folder_path, "publish_tree.yml")
        monitor_file_path = os.path.join(tmp_folder_path, "monitor.yml")

        # finally, save the publish tree and the monitor data to the files
        publish_tree.save_file(self.__TREE_FILE_PATH)
        with open(monitor_file_path, "w+") as fp:
            yaml.safe_dump(monitor_data, fp)

        self.logger.info(
            "Background Publish files have been saved on disk.",
            extra={"action_show_folder": {"path": tmp_folder_path}},
        )

        # ------------------------------------------------------------------------

    def _export_maya_fbx(self, item):
        """
        Export Maya scene as FBX with Unreal-optimized settings
        """
        import maya.cmds as cmds
        import maya.mel as mel

        # Get the path
        path = item.properties.get("path", "")
        if not path:
            self.logger.error("No path found for item")
            return False

        # Ensure the publish folder exists
        publish_folder = os.path.dirname(path)
        self.parent.ensure_folder_exists(publish_folder)

        # Prepare FBX export options
        mel.eval('FBXResetExport')
        
        # Set up axis conversion and scale
        mel.eval('FBXExportUpAxis y')
        mel.eval('FBXExportScaleFactor 1')
        
        # Configure FBX version
        mel.eval('FBXExportFileVersion FBX201900')
        
        # Configure geometry export options
        mel.eval('FBXExportSmoothingGroups -v 1')
        mel.eval('FBXExportHardEdges -v 0')
        mel.eval('FBXExportTangents -v 1')
        mel.eval('FBXExportSmoothMesh -v 1')
        mel.eval('FBXExportInstances -v 0')
        mel.eval('FBXExportTriangulate -v 1')
        
        # Configure animation and deformation options
        mel.eval('FBXExportAnimationOnly -v 0')
        mel.eval('FBXExportBakeComplexAnimation -v 1')
        mel.eval('FBXExportBakeComplexStart -v 0')
        mel.eval('FBXExportBakeComplexEnd -v 100')
        mel.eval('FBXExportBakeComplexStep -v 1')
        
        # Configure includes
        mel.eval('FBXExportInAscii -v 0')
        mel.eval('FBXExportLights -v 1')
        mel.eval('FBXExportCameras -v 1')
        mel.eval('FBXExportConstraints -v 1')
        mel.eval('FBXExportSkeletonDefinitions -v 1')
        
        # Configure materials and textures
        mel.eval('FBXExportMaterials -v 1')
        mel.eval('FBXExportTextures -v 1')
        mel.eval('FBXExportEmbeddedTextures -v 0')
        
        try:
            # Get selection state
            selection = cmds.ls(selection=True)
            if selection:
                mel.eval(f'FBXExport -f "{path}" -s')
            else:
                mel.eval(f'FBXExport -f "{path}"')
            
            self.logger.info(f"FBX exported successfully to: {path}")
            
            # Register the published file
            self._register_publish(item, path)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to export FBX: {str(e)}")
            return False

    def _register_publish(self, item, path):
        """
        Register the published file with Shotgun.
        """
        publisher = self.parent
        
        # Get the publish info
        publish_version = publisher.util.get_version_number(path)
        publish_name = publisher.util.get_publish_name(path)
        
        # Create the publish
        publish_data = {
            "tk": publisher.sgtk,
            "context": item.context,
            "comment": item.description,
            "path": path,
            "name": publish_name,
            "version_number": publish_version,
            "published_file_type": "FBX File",
        }
        
        # Register the publish
        publisher.util.register_publish(**publish_data)

    def post_finalize(self, publish_tree):
        """
        퍼블리시 단계가 완료된 후, 마무리 단계 전에 실행되는 메서드입니다.
        
        작동 과정:
        1. 퍼블리시 트리의 모든 아이템을 순회
        2. 각 아이템의 properties를 검사하여 퍼블리시 상태 확인
        3. 필요한 후처리 작업 수행
        
        참고: local_properties는 퍼블리시 플러그인 실행 중에만 접근 가능합니다.
        """
        
        bg_processing = publish_tree.root_item.properties.get("bg_processing")
        in_bg_process = publish_tree.root_item.properties.get("in_bg_process")

        # we only want to run the actions if we're going to publish in background mode but we're not already in the
        # background publishing process
        if bg_processing and not in_bg_process:
            current_engine = sgtk.platform.current_engine()
            bg_publish_app = current_engine.apps.get("tk-multi-bg-publish")
            # launch the background publishing process and show the monitor app
            bg_publish_app.launch_publish_process(self.__TREE_FILE_PATH)
            bg_publish_app.create_panel()
