import unreal

def add_content_browser_menu():

    tool_menus = unreal.ToolMenus.get()

    # Find the context menu in a blank space in the content browser.
    menu_name = "ContentBrowser.FolderContextMenu"
    menu = tool_menus.find_menu(menu_name)

    if not menu:
        unreal.log_warning(f"Menu not found: {menu_name}")
        return
        
    unreal.log(f"Found menu: {menu_name}")
    
    # Add Section
    section_name = "MyCustomSection"
    menu.add_section(
        section_name,
        unreal.Text("My Custom Actions")
    )

    # Add Menu Items
    entry = unreal.ToolMenuEntry(
        name="MyCustomAction",
        type=unreal.MultiBlockType.MENU_ENTRY
    )

    entry.set_label(unreal.Text("Make Folder Structure"))
    
    command_string = """
import unreal
unreal.log("========== Shot Folder Creation ==========")

import create_shot_directory
create_shot_directory.main()
"""
    entry.set_string_command(
        unreal.ToolMenuStringCommandType.PYTHON,
        "PythonCommand",
        command_string
    )
    
    # Add an item to the menu
    menu.add_menu_entry(section_name, entry)
    unreal.log("Added menu entry")
    
    # Apply changes
    tool_menus.refresh_all_widgets()
    unreal.log("All widgets are refreshed.")