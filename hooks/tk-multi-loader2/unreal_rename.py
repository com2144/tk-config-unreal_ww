import unreal
from collections import defaultdict

def get_new_name_and_path(asset_class, original_path):
    """
    Defines a prefix, path rule according to the class of an asset.
    Returns a new path with a prefix, depending on the class of the asset in the source path.
    Return new_name, new_path
    """
    base_name = original_path.split('/')[-1]

    class_rules = {
        'StaticMesh': {
            'prefix': 'SM_',
            'path': '/Game/Assets/SM/',
        },
        'SkeletalMesh': {
            'prefix': 'SK_',
            'path': '/Game/Assets/SK/',
        },
        'Skeleton': {
            'prefix': 'S_',
            'path': '/Game/Assets/S/',
        },
        'PhysicsAsset': {
            'prefix': 'PHY_',
            'path': '/Game/Assets/PHY/',
        },
        'Material': {
            'prefix': 'M_',
            'path': '/Game/Assets/M/',
        },
        'MaterialInstance': {
            'prefix': 'MI_',
            'path': '/Game/Assets/M/MI/',
        },
        'Texture2D': {
            'prefix': 'T_',
            'path': '/Game/Assets/T/',
        },
        'Blueprint': {
            'prefix': 'BP_',
            'path': '/Game/Assets/BP/',
        },
        'AnimSequence': { # UE 5.4
            'prefix': 'AS_',
            'path': '/Game/Assets/AS/',
        },
        'AnimationSequence': { # UE 5.5
            'prefix': 'AS_',
            'path': '/Game/Assets/AS/',
        },
        'AnimBlueprint': {
            'prefix': 'ABP_',
            'path': '/Game/Assets/AS/ABP/',
        },
        'ParticleSystem': { # UE 5.4
            'prefix': 'NS_',
            'path': '/Game/Assets/NS/',
        },
        'NiagaraSystem': {  # UE 5.5
            'prefix': 'NS_',
            'path': '/Game/Assets/NS/',
        }
    }

    if asset_class in class_rules:
        rule = class_rules[asset_class]
        # Remove an existing prefix and add a new one.
        for prefix in class_rules.values():
            if base_name.startswith(prefix['prefix']):
                base_name = base_name[len(prefix['prefix']):]
                break
        new_name = rule['prefix'] + base_name
        new_path = rule['path'] + new_name
        return new_name, new_path

    return base_name, original_path

def list_and_reorganize_assets():
    """
    Renames and reroute all assets in the content browser according to the Unreal Asset Class.
    """
    editor_lib = unreal.EditorAssetLibrary()
    assets_by_class = defaultdict(list)

    # Get all the assets under the Content(Game) path.
    all_assets = editor_lib.list_assets("/Game/", recursive=True, include_folder=False)

    for asset_path in all_assets:
        asset = editor_lib.load_asset(asset_path) # Load to the UE's object system (memory)
        if asset:
            asset_class = asset.get_class().get_name() # Extract the class name of the asset
            _, new_path = get_new_name_and_path(asset_class, asset_path) # New names and paths categorized by class

            # print(f"asset_path : {asset_path}") # /Game/Assets/SM_cat_tower_lkd.SM_cat_tower_lkd
            # print(f"new_path : {new_path}") # /Game/Assets/SM/SM_cat_tower_lkd.SM_cat_tower_lkd

            # Move only if the path has changed
            if not new_path == asset_path:

                # Create a folder if you do not have a new path
                new_folder_path = '/'.join(new_path.split('/')[:-1])
                if not editor_lib.does_directory_exist(new_folder_path):
                    editor_lib.make_directory(new_folder_path)

                asset_path = sanitize_asset_path(asset_path) # /Game/Assets/cat_tower
                new_path = sanitize_asset_path(new_path) # /Game/Assets/SM/SM_cat_tower

                # Move and rename assets
                success = editor_lib.rename_asset(asset_path, new_path)
                if success:
                    print(f"Move successful : {asset_path} -> {new_path}")
                else:
                    print(f"Move Failed : {asset_path}")

            assets_by_class[asset_class].append(new_path)
    

    print("\n=== List of assets by class ===\n")
    for asset_class, assets in sorted(assets_by_class.items()):
        print("-" * 50)
        print(f"\n[{asset_class}] - Total {len(assets)}")
        for asset_path in sorted(assets):
            print(f"  {asset_path}")


def sanitize_asset_path(path):
    """
    In ObjectPath in 'PackageName.ObjectName' format,
    Returns only PackageName parts before the dot.
    """
    return path.split(".")[0]  # Remove part after '.'


if __name__ == "__main__":
    with unreal.ScopedEditorTransaction("Reorganize Assets by Class") as transaction:
        list_and_reorganize_assets()