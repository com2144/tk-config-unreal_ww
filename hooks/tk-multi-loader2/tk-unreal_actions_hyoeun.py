# This file is based on templates provided and copyrighted by Autodesk, Inc.
# This file has been modified by Epic Games, Inc. and is subject to the license
# file included in this repository.

"""
Hook that loads defines all the available actions, broken down by publish type.
"""

import os
import sys
import sgtk
import unreal
import re
import configparser

HookBaseClass = sgtk.get_hook_baseclass()


class UnrealActions(HookBaseClass):

    # public interface - to be overridden by deriving classes

    def generate_actions(self, sg_publish_data, actions, ui_area): # 특정 publish에 대한 action 리스트 생성

        print("*"*10, "generate_actions 함수 실행")
        app = self.parent
        app.log_debug("Generate actions called for UI element %s. "
                      "Actions: %s. Publish Data: %s" % (ui_area, actions, sg_publish_data))

        action_instances = []

        if "import_content" in actions:
            action_instances.append({"name": "import_content",
                                     "params": None,
                                     "caption": "Import into Content Browser",
                                     "description": "This will import the asset into the Unreal Editor Content Browser."})

        return action_instances

    def execute_multiple_actions(self, actions): # 리스트의 각 원소 액션에 대해 execute_actions() 실행

        print("*"*10, "execute_multiple_actions 함수 실행")

        for single_action in actions:
            name = single_action["name"]
            sg_publish_data = single_action["sg_publish_data"]
            params = single_action["params"]
            self.execute_action(name, params, sg_publish_data)

            print("="*10, f"name : {name}")
            print("="*10, f"sg_publish_data : {sg_publish_data}")
            print("="*10, f"params : {params}")

    def execute_action(self, name, params, sg_publish_data): # generate_actions에서 정의된 작업 실행

        print("*"*10, "execute_action 함수 실행")

        app = self.parent
        app.log_debug("Execute action called for action %s. "
                      "Parameters: %s. Publish Data: %s" % (name, params, sg_publish_data))

        # resolve path
        path = self.get_publish_path(sg_publish_data)
        print("*"*10, f"resolve path라는 path 변수 출력 : {path}")
        # C:\show\project_tiger\assets\char\hodol\LOK\pub\fbx\hodol_lookdev.v001.fbx

        if name == "import_content":
            self._import_to_content_browser(path, sg_publish_data)
        else:
            try:
                HookBaseClass.execute_action(self, name, params, sg_publish_data)
            except AttributeError:
                # base class doesn't have the method, so ignore and continue 
                pass

    def _import_to_content_browser(self, path, sg_publish_data): # Unreal API로 FBX 에셋을 콘텐츠 브라우저에 가져옴, 메타데이터를 설정, 브라우저를 해당 에셋으로 동기화
        # ShotGrid 정보(created_by, URL 등)를 기반으로 태그 설정
        # unreal.EditorAssetLibrary를 사용해 메타데이터를 저장

        print("*"*10, "_import_to_content_browser 함수 실행")

        unreal.log("File to import: {}".format(path))

        if not os.path.exists(path):
            raise Exception("File not found on disk - '%s'" % path)

        destination_path, destination_name = self._get_destination_path_and_name(sg_publish_data)

        asset_path = _unreal_import_fbx_asset(path, destination_path, destination_name)
        print("="*20, f"asset_path : {asset_path}")

        if asset_path:
            self._set_asset_metadata(asset_path, sg_publish_data)

            # Focus the Unreal Content Browser on the imported asset
            asset_paths = []
            asset_paths.append(asset_path)
            unreal.EditorAssetLibrary.sync_browser_to_objects(asset_paths)

    def _set_asset_metadata(self, asset_path, sg_publish_data): # 콘텐츠 브라우저에 가져온 에셋에 메타데이터를 추가 (에셋 생성자, shotgun url)
        asset = unreal.EditorAssetLibrary.load_asset(asset_path)

        print("*"*10, "_set_asset_metadata 함수 실행")
        print("*"*20, f"asset : {asset}")

        if not asset:
            return

        engine = sgtk.platform.current_engine()

        # Add a metadata tag for "created_by"
        if "created_by" in sg_publish_data:
            createdby_dict = sg_publish_data["created_by"]
            name = ""
            if "name" in createdby_dict:
                name = createdby_dict["name"]
            elif "id" in createdby_dict:
                name = createdby_dict["id"]

            tag = engine.get_metadata_tag("created_by")

            # print("="*20, f"name : {name}\nid : {id}\ntag : {tag}")

            unreal.EditorAssetLibrary.set_metadata_tag(asset, tag, name)

        # Add a metadata tag for the Shotgun URL
        # Construct the PublishedFile URL from the publish data type and id since
        # the context of a PublishedFile is the Project context
        shotgun_site = self.sgtk.shotgun_url
        type = sg_publish_data["type"]
        id = sg_publish_data["id"]
        url = shotgun_site + "/detail/" + type + "/" + str(id)
        tag = engine.get_metadata_tag("url")

        # print("="*20, f"type : {type}\nid : {id}\nurl : {url}\ntag : {tag}")

        unreal.EditorAssetLibrary.set_metadata_tag(asset, tag, url)
        unreal.EditorAssetLibrary.save_loaded_asset(asset)


    ##############################################################################################################
    # helper methods which can be subclassed in custom hooks to fine tune the behaviour of things

    def _get_destination_path_and_name(self, sg_publish_data): # templates.yml 참조
        """
        Get the destination path and name from the publish data and the templates

        :param sg_publish_data: Shotgun data dictionary with all the standard publish fields.
        :return destination_path that matches a template and destination_name from asset or published file
        """
        print("*"*10, "_get_destination_path_and_name 함수 실행")
        print("*"*10, f"sg_publish_data : {sg_publish_data}")

        # Enable if needed while in development
        self.sgtk.reload_templates()

        # Get the publish context to determine the template to use
        context = self.sgtk.context_from_entity_dictionary(sg_publish_data)

        # Get the destination templates based on the context
        # Assets and Shots supported by default
        # Other entities fall back to Project
        if context.entity is None:
            destination_template = self.sgtk.templates["unreal_loader_project_path"]
            destination_name_template = self.sgtk.templates["unreal_loader_project_name"]

        elif context.entity["type"] == "Asset":
            destination_template = self.sgtk.templates["unreal_loader_asset_path"]
            destination_name_template = self.sgtk.templates["unreal_loader_asset_name"]

        elif context.entity["type"] == "Shot":
            destination_template = self.sgtk.templates["unreal_loader_shot_path"]
            destination_name_template = self.sgtk.templates["unreal_loader_shot_name"]

        else:
            destination_template = self.sgtk.templates["unreal_loader_project_path"]
            destination_name_template = self.sgtk.templates["unreal_loader_project_name"]


        # 실제로 destination_path, name이 생성되는 부분은 여기서부터
        # Get the name field from the Publish Data
        name = sg_publish_data["name"]
        name = os.path.splitext(name)[0]

        # Query the fields needed for the destination template from the context
        fields = context.as_template_fields(destination_template)

        print("*"*10, "_get_destination_path_and_name 함수 name, field 변수 확인")
        print("*"*10, f"name : {name}")
        print("*"*10, f"fields = {fields}")

        # Add the name field from the publish data
        fields["name"] = name

        # Get destination path by applying fields to destination template
        # Fall back to the root level if unsuccessful
        try:
            destination_path = destination_template.apply_fields(fields)
        except Exception:
            destination_path = "/Game/Assets/"

        # Query the fields needed for the name template from the context
        name_fields = context.as_template_fields(destination_name_template)

        # Add the name field from the publish data
        name_fields["name"] = name

        # Get destination name by applying fields to the name template
        # Fall back to the filename if unsuccessful
        try:
            destination_name = destination_name_template.apply_fields(name_fields)
        except Exception:
            destination_name = _sanitize_name(sg_publish_data["code"])

        print("*"*10, "_get_destination_path_and_name 함수 리턴 값 확인")
        print("*"*10, f"destination_path : {destination_path}")
        print("*"*10, f"destination_name : {destination_name}")

        return destination_path, destination_name


"""
Functions to import FBX into Unreal
"""


def _sanitize_name(name): # 에셋 이름에서 버전 번호 제거
    
    print("*"*10, "_sanitize_name 함수 실행")

    # Remove the default Shotgun versioning number if found (of the form '.v001')
    name_no_version = re.sub(r'.v[0-9]{3}', '', name)

    # Replace any remaining '.' with '_' since they are not allowed in Unreal asset names
    return name_no_version.replace('.', '_')

def _unreal_import_fbx_asset(input_path, destination_path, destination_name): # fbx 어셋을 unreal로 가져옴. 첫번째로 가져온 객체의 경로
    """
    Import an FBX into Unreal Content Browser

    :param input_path: The fbx file to import
    :param destination_path: The Content Browser path where the asset will be placed
    :param destination_name: The asset name to use; if None, will use the filename without extension
    """

    print("*"*10, "_unreal_import_fbx_asset 함수 실행")

    tasks = []
    tasks.append(_generate_fbx_import_task(input_path, destination_path, destination_name))

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)

    first_imported_object = None

    for task in tasks:
        unreal.log("Import Task for: {}".format(task.filename))
        for object_path in task.imported_object_paths:
            unreal.log("Imported object: {}".format(object_path))
            if not first_imported_object:
                first_imported_object = object_path


    # packages/win 디렉토리 경로 설정
    win_dir = os.path.abspath(os.path.dirname(__file__))
    # C:\Users\admin\AppData\Roaming\Shotgun\bundle_cache\gitbranch\tk-config-unreal_ww.git\00f00de\hooks\tk-multi-loader2

    # sys.path에 경로 추가
    if win_dir not in sys.path:
        sys.path.append(win_dir)

    import unreal_rename
    import save_all_assets
    save_all_assets.save_all_unsaved_assets()
    unreal_rename.list_and_reorganize_assets()

    return first_imported_object

def _generate_fbx_import_task( # Unreal의 AssetImportTask 객체 구성, import_asset_tasks 메서드로 실행
    filename,
    destination_path,
    destination_name=None,
    replace_existing=True,
    automated=True,
    save=True,
    materials=True,
    textures=True,
    as_skeletal=False,
    import_animations=False  # 애니메이션 import 옵션 추가
):
    """
    Create and configure an Unreal AssetImportTask

    :param filename: The fbx file to import
    :param destination_path: The Content Browser path where the asset will be placed
    :return the configured AssetImportTask
    """

    print("*"*10, "_generate_fbx_import_task 함수 실행")

    # Create AssetImportTask Object
    task = unreal.AssetImportTask()
    task.filename = filename
    task.destination_path = destination_path

    # By default, destination_name is the filename without the extension
    if destination_name is not None:
        task.destination_name = destination_name

    # Set import options
    task.replace_existing = replace_existing
    task.automated = automated
    task.save = save

    # Set fbx ImportUI Options
    task.options = unreal.FbxImportUI()
    task.options.import_materials = materials
    task.options.import_textures = textures
    task.options.import_as_skeletal = as_skeletal
    # task.options.static_mesh_import_data.combine_meshes = True
    if import_animations:
        print("")
        task.options.import_animations = True
        task.options.animation_length = unreal.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME  # 또는 FBXALIT_ALL_FRAMES
        task.options.import_custom_attribute = True  # 커스텀 애니메이션 어트리뷰트 import
        
        # 필요한 경우 추가 애니메이션 옵션 설정
        # task.options.frames_per_second = 30.0  # FPS 설정
        # task.options.import_bone_tracks = True  # 본 트랙 import
        # task.options.preserve_local_transform = True  # 로컬 트랜스폼 유지

    # 메시 유형 설정
    task.options.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
    if as_skeletal:
        task.options.mesh_type_to_import = unreal.FBXImportType.FBXIT_SKELETAL_MESH

    return task