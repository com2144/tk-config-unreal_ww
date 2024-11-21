import unreal

def save_all_unsaved_assets():
    """
    Find and save all unsaved assets in your content browser.
    """
    editor_lib = unreal.EditorAssetLibrary()
    
    # Get all asset paths
    all_assets = editor_lib.list_assets("/Game/", recursive=True, include_folder=False)
    
    # Count unsaved assets
    unsaved_count = 0
    
    print("Searching for unsaved assets...")

    for asset_path in all_assets:
        # Verify that the asset is modified
        if editor_lib.does_asset_exist(asset_path):
            # Save only the modified(dirty) asset
            if editor_lib.save_asset(asset_path, only_if_is_dirty=True):
                print(f"Saved : {asset_path}")
                unsaved_count += 1

    print(f"Save complete\n{unsaved_count} assets have been saved.")


if __name__ == "__main__":
    with unreal.ScopedEditorTransaction("Save All Unsaved Assets") as transaction:
        save_all_unsaved_assets()