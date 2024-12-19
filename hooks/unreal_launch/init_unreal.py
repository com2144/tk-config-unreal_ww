import unreal

unreal.log("*"*30)
unreal.log("Startup Python Execution")
unreal.log("*"*30)


# Add menu to FolderContextMenu in ContentBrowser
import add_custom_menus
add_custom_menus.add_content_browser_menu()
